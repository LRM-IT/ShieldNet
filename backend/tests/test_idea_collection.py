"""Validation and access-state regressions; no Discord requests."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from pydantic import ValidationError
from app.api.routes import plugin_idea_collection as api


def test_validation():
    text = {"title": "Ideas", "description": "What should we add?"}
    good = {"channel_id": "1520849874529026048", "primary_language": "en", "translations": {"en": text}}
    assert api.SurveyInput(**good).translations["en"].button == "Answer now"
    for changes in ({"primary_language": "ru"}, {"channel_id": "9223372036854775808"},
                    {"translations": {"en": {**text, "title": "x" * 257}}},
                    {"translations": {"en": text, "../": text}}):
        try:
            api.SurveyInput(**{**good, **changes})
        except ValidationError:
            continue
        raise AssertionError(changes)
    try:
        api.AnswerInput(user_id=1, display_name="Member", language="en", text="  ")
    except ValidationError:
        pass
    else:
        raise AssertionError("Whitespace answer accepted")


def test_discord_field_boundaries():
    limits = {"title": 256, "description": 4096, "button": 80, "label": 45,
              "placeholder": 100, "thanks": 2000}
    for field, limit in limits.items():
        values = {"title": "Ideas", "description": "Question", field: "x" * limit}
        assert len(getattr(api.SurveyText(**values), field)) == limit
        try:
            api.SurveyText(**{**values, field: "x" * (limit + 1)})
        except ValidationError:
            continue
        raise AssertionError(f"Accepted oversized {field}")


def test_closed_and_cross_guild():
    async def run():
        session = AsyncMock()
        session.scalar.return_value = None
        try:
            await api.survey_row(session, 111, uuid4())
        except HTTPException as exc:
            assert exc.status_code == 404
        else:
            raise AssertionError("Missing or cross-guild survey accepted")
        row = SimpleNamespace(active=False, message_id=123)
        with patch.object(api, "installation", AsyncMock()), patch.object(api, "survey_row", AsyncMock(return_value=row)):
            try:
                await api.answer(111, uuid4(), api.AnswerInput(user_id=1, display_name="Member", language="en", text="Idea"), session)
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError("Closed survey accepted answer")
        session.execute.assert_not_called()
        session.commit.assert_not_called()
    asyncio.run(run())


def test_expired_publication_lease():
    async def run():
        session = AsyncMock()
        row = SimpleNamespace(claim_id=uuid4(), job_status="processing")
        with patch.object(api, "survey_row", AsyncMock(return_value=row)):
            try:
                await api.complete(111, uuid4(), api.CompleteInput(claim_id=uuid4(), message_id=123), session)
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError("Stale acknowledgement accepted")
        session.commit.assert_not_called()
    asyncio.run(run())


def test_translations_preserved_with_long_ui_label():
    async def run():
        for language in ("vi", "fr"):
            runtime = SimpleNamespace(translate=AsyncMock(side_effect=[
                "Translated survey title longer than forty-five characters",
                "Translated question", "B" * 81, "Idea", "Describe", "Thanks"]))
            with patch.object(api, "require_guild_module", AsyncMock()), patch.object(api, "installation", AsyncMock()), patch.object(api, "AIRuntimeService", return_value=runtime):
                result = await api.translate(111, api.TranslateInput(source_language="en", target_language=language,
                    text=api.SurveyText(title="Ideas", description="Question")), None, AsyncMock())
            assert result["description"] == "Translated question"
            assert len(result["title"]) > 45
            assert result["warnings"][0]["loc"] == ["translations", language, "button"]
            assert result["warnings"][0]["ctx"]["max_length"] == 80
            assert all("system_prompt" in call.kwargs for call in runtime.translate.call_args_list)
    asyncio.run(run())
