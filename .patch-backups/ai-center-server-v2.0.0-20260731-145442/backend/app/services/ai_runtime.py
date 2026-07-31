import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_gateway import GuildAIModuleSetting, GuildAIProvider, GuildAIRequestLog, GuildAIUsage
from app.models.platform_ai import PlatformAIProvider, PlatformAISettings
from app.services.ai_gateway import DEFAULT_BASE_URLS
from app.services.ai_secrets import AISecretService


@dataclass(slots=True)
class AIResult:
    text: str
    model: str | None
    input_units: int
    output_units: int
    latency_ms: int


class AIRuntimeService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(self, *, guild_id: int, module_key: str, capability: str, input_text: str,
                      system_prompt: str | None = None, source_language: str | None = None,
                      target_language: str | None = None, model: str | None = None,
                      temperature: float | None = None, max_output_tokens: int | None = None,
                      metadata: dict[str, Any] | None = None) -> tuple[GuildAIProvider, AIResult]:
        platform_settings = await self.session.get(PlatformAISettings, 1)
        if platform_settings and platform_settings.emergency_stop:
            raise RuntimeError("Platform AI emergency stop is enabled")

        setting = await self._setting(guild_id, module_key, capability)
        candidates = await self._providers(guild_id, setting)
        if not candidates:
            raise LookupError(f"No enabled AI provider configured for {module_key}/{capability}")

        defaults = (platform_settings.defaults or {}) if platform_settings else {}
        platform_default_model = (
            defaults.get(f"{module_key}:{capability}")
            or defaults.get(capability)
            or defaults.get(module_key)
        )

        failures: list[str] = []
        for provider in candidates:
            selected_model = (
                model
                or (setting.model if setting else None)
                or provider.default_model
                or platform_default_model
            )
            try:
                result = await self._call_provider(
                    provider=provider, capability=capability, input_text=input_text,
                    system_prompt=system_prompt, source_language=source_language,
                    target_language=target_language, model=selected_model,
                    temperature=temperature, max_output_tokens=max_output_tokens,
                )
                await self._record(provider, guild_id, module_key, capability, result, "success", metadata or {})
                await self.session.commit()
                return provider, result
            except Exception as exc:
                failures.append(f"{provider.name}: {str(exc)[:250]}")
                await self._record_failure(provider, guild_id, module_key, capability, selected_model, exc, metadata or {})
                await self.session.commit()
        raise RuntimeError("All configured AI providers failed: " + " | ".join(failures))

    async def _setting(self, guild_id: int, module_key: str, capability: str) -> GuildAIModuleSetting | None:
        result = await self.session.execute(select(GuildAIModuleSetting).where(
            GuildAIModuleSetting.guild_id == guild_id,
            GuildAIModuleSetting.module_key == module_key,
            GuildAIModuleSetting.capability == capability,
            GuildAIModuleSetting.enabled.is_(True),
        ))
        return result.scalar_one_or_none()

    async def _providers(
        self,
        guild_id: int,
        setting: GuildAIModuleSetting | None,
    ) -> list[GuildAIProvider | PlatformAIProvider]:
        ids: list[UUID] = []
        if setting and setting.provider_id:
            ids.append(setting.provider_id)
        if setting:
            for raw in setting.fallback_provider_ids or []:
                try:
                    value = UUID(str(raw))
                    if value not in ids:
                        ids.append(value)
                except ValueError:
                    continue

        query = select(GuildAIProvider).where(
            GuildAIProvider.guild_id == guild_id,
            GuildAIProvider.enabled.is_(True),
        )
        result = await self.session.execute(
            query.order_by(GuildAIProvider.priority, GuildAIProvider.name)
        )
        available = list(result.scalars().all())

        if ids:
            by_id = {item.id: item for item in available}
            available = [by_id[item_id] for item_id in ids if item_id in by_id]

        if available:
            return available

        platform_result = await self.session.execute(
            select(PlatformAIProvider)
            .where(PlatformAIProvider.enabled.is_(True))
            .order_by(
                PlatformAIProvider.priority,
                PlatformAIProvider.name,
            )
        )
        return list(platform_result.scalars().all())

    async def _call_provider(self, *, provider: GuildAIProvider, capability: str, input_text: str,
                             system_prompt: str | None, source_language: str | None,
                             target_language: str | None, model: str | None,
                             temperature: float | None, max_output_tokens: int | None) -> AIResult:
        started = time.perf_counter()
        key = AISecretService.decrypt(provider.encrypted_api_key)
        base = (provider.api_base_url or DEFAULT_BASE_URLS.get(provider.provider_type) or "").rstrip("/")
        if not base:
            raise ValueError("Provider API base URL is missing")
        prompt = self._prompt(capability, input_text, system_prompt, source_language, target_language)
        async with httpx.AsyncClient(timeout=provider.timeout_seconds, follow_redirects=True) as client:
            if provider.provider_type in {"openai", "xai", "groq", "openai_compatible"}:
                data = await self._openai(client, base, key, model, prompt, temperature, max_output_tokens, provider)
            elif provider.provider_type == "anthropic":
                data = await self._anthropic(client, base, key, model, prompt, temperature, max_output_tokens)
            elif provider.provider_type == "gemini":
                data = await self._gemini(client, base, key, model, prompt, temperature, max_output_tokens)
            elif provider.provider_type in {"deepl", "google_translate", "libretranslate"}:
                data = await self._translation(client, provider.provider_type, base, key, input_text, source_language, target_language)
            else:
                raise ValueError(f"Unsupported AI provider type: {provider.provider_type}")
        data.latency_ms = int((time.perf_counter() - started) * 1000)
        return data

    @staticmethod
    def _prompt(capability: str, text: str, system_prompt: str | None, source: str | None, target: str | None) -> str:
        if capability == "translation" or target:
            direction = f" from {source}" if source and source != "auto" else ""
            instruction = f"Translate the following text{direction} to {target or 'the requested target language'}. Preserve Discord mentions, URLs, Markdown, emoji, names and line breaks. Return only the translation."
        else:
            instruction = system_prompt or "Respond to the supplied input accurately and concisely."
        if system_prompt and capability == "translation":
            instruction += "\nAdditional rules: " + system_prompt
        return instruction + "\n\nINPUT:\n" + text

    async def _openai(self, client, base, key, model, prompt, temperature, max_tokens, provider) -> AIResult:
        if not model:
            raise ValueError("Model is required")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if provider.organization_id:
            headers["OpenAI-Organization"] = provider.organization_id
        if provider.project_id:
            headers["OpenAI-Project"] = provider.project_id
        payload: dict[str, Any] = {"model": model, "input": prompt, "store": False}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        response = await client.post(f"{base}/responses", headers=headers, json=payload)
        if response.status_code == 404:
            chat_payload: dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            if temperature is not None: chat_payload["temperature"] = temperature
            if max_tokens is not None: chat_payload["max_tokens"] = max_tokens
            response = await client.post(f"{base}/chat/completions", headers=headers, json=chat_payload)
            self._raise(response)
            body = response.json(); choice = (body.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or "").strip(); usage = body.get("usage") or {}
            return AIResult(text, model, int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0), 0)
        self._raise(response)
        body = response.json(); text = body.get("output_text") or ""
        if not text:
            text = "".join(c.get("text", "") for o in body.get("output", []) for c in o.get("content", []) if c.get("type") == "output_text")
        usage = body.get("usage") or {}
        return AIResult(text.strip(), model, int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0), 0)

    async def _anthropic(self, client, base, key, model, prompt, temperature, max_tokens) -> AIResult:
        if not model: raise ValueError("Model is required")
        payload: dict[str, Any] = {"model": model, "max_tokens": max_tokens or 2048, "messages": [{"role": "user", "content": prompt}]}
        if temperature is not None: payload["temperature"] = temperature
        response = await client.post(f"{base}/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, json=payload)
        self._raise(response); body = response.json()
        text = "".join(x.get("text", "") for x in body.get("content", []) if x.get("type") == "text")
        usage = body.get("usage") or {}
        return AIResult(text.strip(), model, int(usage.get("input_tokens", 0) or 0), int(usage.get("output_tokens", 0) or 0), 0)

    async def _gemini(self, client, base, key, model, prompt, temperature, max_tokens) -> AIResult:
        if not model: raise ValueError("Model is required")
        generation: dict[str, Any] = {}
        if temperature is not None: generation["temperature"] = temperature
        if max_tokens is not None: generation["maxOutputTokens"] = max_tokens
        response = await client.post(f"{base}/models/{model}:generateContent?key={key}", json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation})
        self._raise(response); body = response.json()
        candidates = body.get("candidates") or []; parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        text = "".join(p.get("text", "") for p in parts)
        usage = body.get("usageMetadata") or {}
        return AIResult(text.strip(), model, int(usage.get("promptTokenCount", 0) or 0), int(usage.get("candidatesTokenCount", 0) or 0), 0)

    async def _translation(self, client, provider_type, base, key, text, source, target) -> AIResult:
        if not target: raise ValueError("target_language is required")
        if provider_type == "deepl":
            payload = {"text": [text], "target_lang": target.upper()}
            if source and source != "auto": payload["source_lang"] = source.upper()
            response = await client.post(f"{base}/translate", headers={"Authorization": f"DeepL-Auth-Key {key}"}, data=payload)
            self._raise(response); output = ((response.json().get("translations") or [{}])[0].get("text") or "")
        elif provider_type == "google_translate":
            payload = {"q": text, "target": target, "format": "text"}
            if source and source != "auto": payload["source"] = source
            response = await client.post(f"{base}?key={key}", json=payload); self._raise(response)
            output = (((response.json().get("data") or {}).get("translations") or [{}])[0].get("translatedText") or "")
        else:
            payload = {"q": text, "source": source or "auto", "target": target, "format": "text"}
            if key: payload["api_key"] = key
            response = await client.post(f"{base}/translate", json=payload); self._raise(response)
            output = response.json().get("translatedText") or ""
        return AIResult(output.strip(), None, 0, 0, 0)

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise RuntimeError(f"Provider HTTP {response.status_code}: {response.text[:500]}")

    @staticmethod
    def _provider_log_data(provider, metadata):
        is_platform = isinstance(provider, PlatformAIProvider)
        result = dict(metadata)
        if is_platform:
            result.update({
                "provider_scope": "platform",
                "platform_provider_id": str(provider.id),
                "platform_provider_name": provider.name,
            })
        else:
            result.setdefault("provider_scope", "guild")
        return (None if is_platform else provider.id), result

    async def _record(self, provider, guild_id, module_key, capability, result, status, metadata):
        provider_id, metadata_json = self._provider_log_data(provider, metadata)
        self.session.add(GuildAIUsage(
            guild_id=guild_id,
            provider_id=provider_id,
            module_key=module_key,
            capability=capability,
            model=result.model,
            input_units=result.input_units,
            output_units=result.output_units,
        ))
        self.session.add(GuildAIRequestLog(
            guild_id=guild_id,
            provider_id=provider_id,
            module_key=module_key,
            capability=capability,
            model=result.model,
            status=status,
            latency_ms=result.latency_ms,
            metadata_json=metadata_json,
        ))

    async def _record_failure(self, provider, guild_id, module_key, capability, model, exc, metadata):
        provider_id, metadata_json = self._provider_log_data(provider, metadata)
        self.session.add(GuildAIRequestLog(
            guild_id=guild_id,
            provider_id=provider_id,
            module_key=module_key,
            capability=capability,
            model=model,
            status="error",
            error_code=exc.__class__.__name__,
            error_message=str(exc)[:2000],
            metadata_json=metadata_json,
        ))
