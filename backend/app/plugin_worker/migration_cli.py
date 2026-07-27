from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from app.plugin_worker.migration_preflight import run_migration_preflight

def load_checksums(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Installed checksums must be a JSON object")
    result = {}
    for name, checksum in data.items():
        if not isinstance(name, str) or not isinstance(checksum, str):
            raise ValueError("Checksum keys and values must be strings")
        checksum = checksum.lower().strip()
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError(f"Invalid SHA-256 for {name}")
        result[name] = checksum
    return result

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only ShieldNet plugin migration preflight")
    parser.add_argument("plugin_root", type=Path)
    parser.add_argument("--plugin-key", required=True)
    parser.add_argument("--installed-checksums", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        result = run_migration_preflight(
            args.plugin_root,
            plugin_key=args.plugin_key,
            installed_checksums=load_checksums(args.installed_checksums),
        )
        payload = {
            "ok": True,
            "plugin_key": result.plugin_key,
            "plugin_root": str(result.plugin_root),
            "schema_name": result.schema_name,
            "migration_count": len(result.migrations),
            "pending_count": len(result.pending),
            "plan": [
                {
                    "order": item.order,
                    "filename": item.filename,
                    "status": item.status.value,
                    "checksum_sha256": item.checksum_sha256,
                    "installed_checksum_sha256": item.installed_checksum_sha256,
                }
                for item in result.plan
            ],
        }
    except Exception as exc:
        payload = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Migration preflight failed: {payload['error_type']}: {payload['error']}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Plugin: {payload['plugin_key']}")
        print(f"Root: {payload['plugin_root']}")
        print(f"Schema: {payload['schema_name']}")
        print(f"Migrations: {payload['migration_count']}")
        print(f"Pending: {payload['pending_count']}")
        print("Plan:")
        for item in payload["plan"]:
            print(f"  {item['order']:04d} {item['filename']} [{item['status']}]")
        if not payload["plan"]:
            print("  no migrations")
        print("Preflight result: OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
