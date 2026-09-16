"""List literal strings in Angular components that are absent from _phrases."""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "admin-frontend" / "src" / "app"
ENGLISH = ROOT / "admin-frontend" / "public" / "locales" / "en.json"

parser = argparse.ArgumentParser()
parser.add_argument("--locale", default="en")
args = parser.parse_args()
english = json.loads(ENGLISH.read_text(encoding="utf-8"))
locale_path = ENGLISH.with_name(f"{args.locale}.json")
localized = json.loads(locale_path.read_text(encoding="utf-8"))

known: dict[str, str] = {}
def collect(left, right):
    if isinstance(left, str) and isinstance(right, str):
        known[left] = right
    elif isinstance(left, dict) and isinstance(right, dict):
        for key, value in left.items():
            if key not in {"_language", "_phrases"} and key in right:
                collect(value, right[key])
collect(english, localized)
known.update(localized.get("_phrases", {}))
sys.stdout.reconfigure(encoding="utf-8")
counter: collections.Counter[str] = collections.Counter()
pattern = re.compile(r'>([^<>{}@\n][^<>{}\n]*?)<|(?:placeholder|title|aria-label)="([^"]+)"')

for path in SOURCE.rglob("*.component.ts"):
    source = path.read_text(encoding="utf-8")
    for match in pattern.finditer(source):
        value = (match.group(1) or match.group(2)).strip()
        if value and re.search(r"[A-Za-zА-Яа-яІіЇїЄє]", value) and not value.startswith(("$", "[", "(")):
            counter[value] += 1

missing = [(value, count) for value, count in counter.most_common() if value not in known]
translated = sum(count for value, count in counter.items() if value in known and known[value] != value)
total = sum(counter.values())
print(f"locale={args.locale} literals={total} translated={translated} missing={sum(x[1] for x in missing)}")
for value, count in missing:
    print(f"{count:3} | {value}")
