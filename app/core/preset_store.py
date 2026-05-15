"""File-based parameter preset library.

Stores presets in data/presets.json as a flat JSON array.
Thread-safe for single-process usage (no concurrent writes expected).
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

DATA_FILE = Path("data/presets.json")


def _now() -> str:
    return datetime.now().isoformat(timespec="microseconds")


def _load() -> List[dict]:
    if not DATA_FILE.exists():
        _save([])
    text = DATA_FILE.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else []


def _save(presets: List[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Public API ────────────────────────────────────────────────────────

def list_presets(search: str = "", category: str = "") -> List[dict]:
    presets = _load()
    if search:
        q = search.lower()
        presets = [
            p for p in presets
            if q in p["name"].lower()
            or any(q in t.lower() for t in p.get("tags", []))
        ]
    if category:
        presets = [p for p in presets if p.get("category", "") == category]
    return sorted(presets, key=lambda p: p.get("updated_at", ""), reverse=True)


def get_categories() -> List[str]:
    return sorted({p.get("category", "") for p in _load() if p.get("category")})


def create_preset(
    name: str,
    params: dict,
    curve_params: dict,
    category: str = "",
    tags: Optional[List[str]] = None,
) -> dict:
    presets = _load()
    now = _now()
    item = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "category": category.strip(),
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "params": params,
        "curve_params": curve_params,
        "created_at": now,
        "updated_at": now,
    }
    presets.append(item)
    _save(presets)
    return item


def get_preset(preset_id: str) -> Optional[dict]:
    for p in _load():
        if p["id"] == preset_id:
            return p
    return None


def update_preset(
    preset_id: str,
    name: Optional[str] = None,
    params: Optional[dict] = None,
    curve_params: Optional[dict] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[dict]:
    presets = _load()
    for i, p in enumerate(presets):
        if p["id"] == preset_id:
            if name is not None:
                p["name"] = name.strip()
            if params is not None:
                p["params"] = params
            if curve_params is not None:
                p["curve_params"] = curve_params
            if category is not None:
                p["category"] = category.strip()
            if tags is not None:
                p["tags"] = [t.strip() for t in tags if t.strip()]
            p["updated_at"] = _now()
            presets[i] = p
            _save(presets)
            return p
    return None


def delete_preset(preset_id: str) -> bool:
    presets = _load()
    filtered = [p for p in presets if p["id"] != preset_id]
    if len(filtered) < len(presets):
        _save(filtered)
        return True
    return False
