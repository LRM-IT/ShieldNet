import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_gateway import GuildAIProvider, GuildAIRequestLog, GuildAIRoute, GuildAIRouteTarget, GuildAIUsage
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
    """Central server AI entry point used by every plugin.

    Plugins specify only guild_id, module_key and capability. Provider selection,
    retries, fallback and circuit breaking are resolved from the server AI Center.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(self, *, guild_id: int, module_key: str, capability: str, input_text: str,
                      system_prompt: str | None = None, source_language: str | None = None,
                      target_language: str | None = None, model: str | None = None,
                      temperature: float | None = None, max_output_tokens: int | None = None,
                      metadata: dict[str, Any] | None = None) -> tuple[GuildAIProvider, AIResult]:
        route = await self._route(guild_id, capability)
        if route is None or not route.enabled:
            raise LookupError(f"No enabled server AI route configured for capability '{capability}'")

        targets = await self._targets(route)
        if not targets:
            raise LookupError(f"AI route '{capability}' has no enabled providers")

        failures: list[str] = []
        attempts = 0
        for target, provider in targets:
            if attempts >= route.max_total_attempts:
                break
            if provider.circuit_open_until and provider.circuit_open_until > datetime.now(timezone.utc):
                failures.append(f"{provider.name}: circuit open")
                continue

            retry_count = max(0, target.retries)
            for retry in range(retry_count + 1):
                if attempts >= route.max_total_attempts:
                    break
                attempts += 1
                selected_model = model or target.model or provider.default_model
                try:
                    result = await self._call_provider(
                        provider=provider, capability=capability, input_text=input_text,
                        system_prompt=system_prompt, source_language=source_language,
                        target_language=target_language, model=selected_model,
                        temperature=temperature, max_output_tokens=max_output_tokens,
                        timeout_seconds=target.timeout_seconds,
                    )
                    provider.consecutive_failures = 0
                    provider.circuit_open_until = None
                    provider.last_error = None
                    await self._record(provider, guild_id, module_key, capability, result, "success", {
                        **(metadata or {}), "route_id": str(route.id), "route_position": target.position,
                        "attempt": attempts, "retry": retry,
                    })
                    await self.session.commit()
                    return provider, result
                except Exception as exc:
                    failures.append(f"{provider.name}[{attempts}]: {str(exc)[:250]}")
                    provider.consecutive_failures = (provider.consecutive_failures or 0) + 1
                    provider.last_error = str(exc)[:2000]
                    if provider.consecutive_failures >= route.failure_threshold:
                        provider.circuit_open_until = datetime.now(timezone.utc) + timedelta(seconds=route.cooldown_seconds)
                    await self._record_failure(provider, guild_id, module_key, capability, selected_model, exc, {
                        **(metadata or {}), "route_id": str(route.id), "route_position": target.position,
                        "attempt": attempts, "retry": retry,
                    })
                    await self.session.commit()
                    if retry < retry_count:
                        await asyncio.sleep(min(2 ** retry, 5))

        raise RuntimeError("All providers in the server AI route failed: " + " | ".join(failures))

    async def translate(self, *, guild_id: int, module_key: str, text: str,
                        target_language: str, source_language: str = "auto",
                        **kwargs: Any) -> str:
        _, result = await self.execute(
            guild_id=guild_id, module_key=module_key, capability="translation",
            input_text=text, source_language=source_language, target_language=target_language, **kwargs,
        )
        return result.text

    async def recognize(self, *, guild_id: int, module_key: str, text: str,
                        instruction: str | None = None, **kwargs: Any) -> str:
        _, result = await self.execute(
            guild_id=guild_id, module_key=module_key, capability="recognition",
            input_text=text, system_prompt=instruction, **kwargs,
        )
        return result.text

    async def _route(self, guild_id: int, capability: str) -> GuildAIRoute | None:
        result = await self.session.execute(select(GuildAIRoute).where(
            GuildAIRoute.guild_id == guild_id,
            GuildAIRoute.capability == capability.strip().lower(),
        ))
        return result.scalar_one_or_none()

    async def _targets(self, route: GuildAIRoute) -> list[tuple[GuildAIRouteTarget, GuildAIProvider]]:
        result = await self.session.execute(
            select(GuildAIRouteTarget, GuildAIProvider)
            .join(GuildAIProvider, GuildAIProvider.id == GuildAIRouteTarget.provider_id)
            .where(
                GuildAIRouteTarget.route_id == route.id,
                GuildAIRouteTarget.enabled.is_(True),
                GuildAIProvider.guild_id == route.guild_id,
                GuildAIProvider.enabled.is_(True),
            )
            .order_by(GuildAIRouteTarget.position)
        )
        return list(result.all())

    async def _call_provider(self, *, provider: GuildAIProvider, capability: str, input_text: str,
                             system_prompt: str | None, source_language: str | None,
                             target_language: str | None, model: str | None,
                             temperature: float | None, max_output_tokens: int | None,
                             timeout_seconds: int | None) -> AIResult:
        started = time.perf_counter()
        key = AISecretService.decrypt(provider.encrypted_api_key)
        base = (provider.api_base_url or DEFAULT_BASE_URLS.get(provider.provider_type) or "").rstrip("/")
        if not base:
            raise ValueError("Provider API base URL is missing")
        prompt = self._prompt(capability, input_text, system_prompt, source_language, target_language)
        timeout = timeout_seconds or provider.timeout_seconds
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
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
            instruction = system_prompt or "Analyze the supplied input and return only the requested result."
        if system_prompt and capability == "translation":
            instruction += "\nAdditional rules: " + system_prompt
        return instruction + "\n\nINPUT:\n" + text

    async def _openai(self, client, base, key, model, prompt, temperature, max_tokens, provider) -> AIResult:
        if not model: raise ValueError("Model is required")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if provider.organization_id: headers["OpenAI-Organization"] = provider.organization_id
        if provider.project_id: headers["OpenAI-Project"] = provider.project_id
        payload: dict[str, Any] = {"model": model, "input": prompt, "store": False}
        if temperature is not None: payload["temperature"] = temperature
        if max_tokens is not None: payload["max_output_tokens"] = max_tokens
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

    async def _record(self, provider, guild_id, module_key, capability, result, status, metadata):
        self.session.add(GuildAIUsage(guild_id=guild_id, provider_id=provider.id, module_key=module_key,
            capability=capability, model=result.model, input_units=result.input_units, output_units=result.output_units))
        self.session.add(GuildAIRequestLog(guild_id=guild_id, provider_id=provider.id, module_key=module_key,
            capability=capability, model=result.model, status=status, latency_ms=result.latency_ms, metadata_json=metadata))

    async def _record_failure(self, provider, guild_id, module_key, capability, model, exc, metadata):
        self.session.add(GuildAIRequestLog(guild_id=guild_id, provider_id=provider.id, module_key=module_key,
            capability=capability, model=model, status="error", error_code=exc.__class__.__name__,
            error_message=str(exc)[:2000], metadata_json=metadata))
