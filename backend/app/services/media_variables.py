from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class MediaVariable:
    key: str
    label: str
    group: str
    value_type: str = "text"
    sample: Any = ""
    repeatable: bool = False

    def serialize(self) -> dict[str, Any]:
        data = asdict(self)
        data["token"] = "{{" + self.key + "}}"
        return data

COMMON = [
    MediaVariable("TITLE", "Title", "Common", sample="Voting results"),
    MediaVariable("DESCRIPTION", "Description", "Common", sample="Thank you for participating!"),
    MediaVariable("DATE", "Date", "Common", sample="2026-08-04"),
    MediaVariable("SERVER_NAME", "Server name", "Common", sample="Server 2279"),
    MediaVariable("SERVER_ICON", "Server icon", "Common", value_type="image"),
    MediaVariable("GAME_NAME", "Game name", "Common", sample="Last War"),
    MediaVariable("GAME_ICON", "Game icon", "Common", value_type="image"),
    MediaVariable("QR_URL", "QR destination", "Common", value_type="url", sample="https://discord.lrm-it.com"),
    MediaVariable("QR_CAPTION", "QR caption", "Common", sample="Visit our website"),
]

VOTING = [
    MediaVariable("TOTAL_VOTES", "Total votes", "Voting", value_type="number", sample=128),
    MediaVariable("WINNER_LABEL", "Winner label", "Voting", sample="NAP 15"),
    MediaVariable("WINNER_VOTES", "Winner votes", "Voting", value_type="number", sample=72),
    MediaVariable("WINNER_PERCENTAGE", "Winner percentage", "Voting", value_type="percentage", sample=56.3),
    MediaVariable("OPTION_POSITION", "Option position", "Voting options", value_type="number", sample=1, repeatable=True),
    MediaVariable("OPTION_LABEL", "Option label", "Voting options", sample="NAP 15", repeatable=True),
    MediaVariable("OPTION_VOTES", "Option votes", "Voting options", value_type="number", sample=72, repeatable=True),
    MediaVariable("OPTION_PERCENTAGE", "Option percentage", "Voting options", value_type="percentage", sample=56.3, repeatable=True),
]

RANKS = [
    MediaVariable("RANK_TITLE", "Ranking title", "Ranks", sample="Power ranking"),
    MediaVariable("RANK_PERIOD", "Ranking period", "Ranks", sample="Season 1"),
    MediaVariable("ENTRY_POSITION", "Position", "Rank entries", value_type="number", sample=1, repeatable=True),
    MediaVariable("ENTRY_NAME", "Name", "Rank entries", sample="Player name", repeatable=True),
    MediaVariable("ENTRY_VALUE", "Value", "Rank entries", sample="245.8M", repeatable=True),
    MediaVariable("ENTRY_AVATAR", "Avatar", "Rank entries", value_type="image", repeatable=True),
]

SCHEMAS = {"common": COMMON, "voting": COMMON + VOTING, "ranks": COMMON + RANKS}

def list_variables(schema: str | None = None) -> list[dict[str, Any]]:
    return [item.serialize() for item in SCHEMAS.get(schema or "common", SCHEMAS["common"])]

def sample_data(schema: str) -> dict[str, Any]:
    return {item.key: item.sample for item in SCHEMAS.get(schema, SCHEMAS["common"]) if not item.repeatable}

def validate_tokens(schema: str, tokens: list[str]) -> dict[str, Any]:
    allowed = {item.key for item in SCHEMAS.get(schema, SCHEMAS["common"])}
    normalized = [token.strip().upper().replace("{{", "").replace("}}", "") for token in tokens]
    invalid = sorted({token for token in normalized if token and token not in allowed})
    return {"valid": not invalid, "invalid": invalid, "allowed": sorted(allowed)}
