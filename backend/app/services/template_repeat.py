from __future__ import annotations
from copy import deepcopy
from typing import Any

def expand_repeat_layers(layers: list[dict[str, Any]], data: dict[str, Any]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for layer in layers:
        if layer.get("type") != "repeat":
            expanded.append(layer)
            continue
        items = data.get(str(layer.get("source") or "OPTIONS").upper())
        if not isinstance(items, list):
            items = []
        base_x = int(layer.get("x") or 0)
        base_y = int(layer.get("y") or 0)
        row_height = max(1, int(layer.get("height") or 80))
        gap = max(0, int(layer.get("gap") or 0))
        maximum = max(1, min(50, int(layer.get("maxItems") or 10)))
        for index, raw_item in enumerate(items[:maximum]):
            item = raw_item if isinstance(raw_item, dict) else {"LABEL": str(raw_item)}
            values = {
                "ITEM_INDEX": index,
                "ITEM_POSITION": item.get("POSITION", index + 1),
                "ITEM_LABEL": item.get("LABEL", ""),
                "ITEM_VOTES": item.get("VOTES", 0),
                "ITEM_PERCENTAGE": item.get("PERCENTAGE", 0),
                "ITEM_IS_WINNER": item.get("IS_WINNER", False),
            }
            for child in layer.get("children") or []:
                clone = deepcopy(child)
                clone["id"] = f"{layer.get('id', 'repeat')}:{index}:{child.get('id', 'child')}"
                clone["x"] = base_x + int(child.get("x") or 0)
                clone["y"] = base_y + index * (row_height + gap) + int(child.get("y") or 0)
                clone["zIndex"] = int(layer.get("zIndex") or 0) + int(child.get("zIndex") or 0)
                for field in ("text", "variable"):
                    value = clone.get(field)
                    if isinstance(value, str):
                        for key, replacement in values.items():
                            value = value.replace("{{" + key + "}}", str(replacement))
                        clone[field] = value
                expanded.append(clone)
    return expanded
