"""List literal strings in Angular components that are absent from _phrases."""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "admin-frontend" / "src" / "app"
ENGLISH = ROOT / "admin-frontend" / "public" / "locales" / "en.json"

document = json.loads(ENGLISH.read_text(encoding="utf-8"))
known = set(document.get("_phrases", {}))
sys.stdout.reconfigure(encoding="utf-8")
counter: collections.Counter[str] = collections.Counter()
pattern = re.compile(r'>([^<>{}@\n][^<>{}\n]*?)<|(?:placeholder|title|aria-label)="([^"]+)"')

for path in SOURCE.rglob("*.component.ts"):
    source = path.read_text(encoding="utf-8")
    for match in pattern.finditer(source):
        value = (match.group(1) or match.group(2)).strip()
        if value and re.search(r"[A-Za-zА-Яа-яІіЇїЄє]", value) and not value.startswith(("$", "[", "(")):
            counter[value] += 1

for value, count in counter.most_common():
    if value not in known:
        print(f"{count:3} | {value}")
