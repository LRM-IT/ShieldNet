"""Generate localized plugin documentation through the configured AI Center route."""
import argparse
import asyncio
import json
from pathlib import Path

from app.db.session import AsyncSessionFactory, close_database
from app.services.ai_runtime import AIRuntimeService

LANGUAGES = {"uk":"Ukrainian","ru":"Russian","de":"German","ar":"Arabic","fr":"French","it":"Italian","pl":"Polish"}


def clean_json(value: str) -> dict:
    text = value.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--guild-id", type=int, required=True)
    parser.add_argument("--docs-dir", type=Path, required=True)
    parser.add_argument("--languages", default=",".join(LANGUAGES))
    args = parser.parse_args()
    source = json.loads((args.docs_dir / "en.json").read_text(encoding="utf-8"))
    source_text = json.dumps(source, ensure_ascii=False, indent=2)
    requested = [code.strip() for code in args.languages.split(",") if code.strip()]
    async with AsyncSessionFactory() as session:
        runtime = AIRuntimeService(session)
        for code in requested:
            language = LANGUAGES[code]
            translated = await runtime.translate(
                guild_id=args.guild_id,
                module_key="plugin_documentation",
                text=source_text,
                source_language="English",
                target_language=language,
                system_prompt="Return valid JSON only. Preserve every object key, plugin key, {plugin} placeholder and array structure. Translate every human-readable string completely and naturally.",
                temperature=0,
                max_output_tokens=16000,
                metadata={"document":"plugin-docs","locale":code},
            )
            document = clean_json(translated)
            if set(document.get("plugins", {})) != set(source["plugins"]):
                raise ValueError(f"Plugin key mismatch in {code}")
            (args.docs_dir / f"{code}.json").write_text(json.dumps(document, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            print(f"generated {code}.json")
    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
