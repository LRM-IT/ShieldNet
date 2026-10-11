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
                    {"translations": {"en": {**text, "title": "x" * 46}}},
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
