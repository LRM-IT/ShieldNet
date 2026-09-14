import json
from pathlib import Path

from app.plugin_sdk.capabilities import ALL_CAPABILITIES


def test_shipped_plugins_only_request_supported_runtime_capabilities() -> None:
    plugins_root = Path(__file__).resolve().parents[2] / "plugins"
    unknown = {}
    for path in plugins_root.glob("*/plugin.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        unsupported = set(manifest.get("capabilities", [])) - ALL_CAPABILITIES
        if unsupported:
            unknown[manifest["id"]] = sorted(unsupported)
    assert not unknown
