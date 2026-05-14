"""File-based prompt library.

Stores prompts in data/prompts.json as a flat JSON array.
Thread-safe for single-process usage (no concurrent writes expected).
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

DATA_FILE = Path("data/prompts.json")

_SAMPLES = [
    {
        "id": "sample-1",
        "name": "日系小清新",
        "category": "人像",
        "tags": ["日系", "清新", "人像"],
        "prompt": "整体色调偏冷清，轻微提亮，降低饱和度，皮肤通透自然，背景虚化柔和，营造日系清新感",
    },
    {
        "id": "sample-2",
        "name": "胶片复古",
        "category": "日常",
        "tags": ["胶片", "复古", "暖色"],
        "prompt": "添加复古胶片色调，整体偏暖橙，轻微降低对比度，添加细腻颗粒感，轻微暗角，营造90年代胶片氛围",
    },
    {
        "id": "sample-3",
        "name": "通透自然",
        "category": "日常",
        "tags": ["自然", "清透"],
        "prompt": "轻微提亮整体曝光，增加通透感，色调清新自然，适度提高对比度使层次感更强，保持真实感",
    },
    {
        "id": "sample-4",
        "name": "电影感",
        "category": "风景",
        "tags": ["电影", "浓郁", "青橙"],
        "prompt": "青橙色调，提高对比度，压暗阴影，提亮高光，饱和度适中，营造电影感大片氛围",
    },
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load() -> List[dict]:
    if not DATA_FILE.exists():
        # First run: seed with samples
        _save([{**s, "created_at": _now(), "updated_at": _now()} for s in _SAMPLES])
    text = DATA_FILE.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else []


def _save(prompts: List[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Public API ────────────────────────────────────────────────────────

def list_prompts(search: str = "", category: str = "") -> List[dict]:
    prompts = _load()
    if search:
        q = search.lower()
        prompts = [
            p for p in prompts
            if q in p["name"].lower()
            or q in p["prompt"].lower()
            or any(q in t.lower() for t in p.get("tags", []))
        ]
    if category:
        prompts = [p for p in prompts if p.get("category", "") == category]
    return sorted(prompts, key=lambda p: p.get("updated_at", ""), reverse=True)


def get_categories() -> List[str]:
    return sorted({p.get("category", "") for p in _load() if p.get("category")})


def create_prompt(name: str, prompt: str, category: str = "", tags: List[str] = None) -> dict:
    prompts = _load()
    now = _now()
    item = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "category": category.strip(),
        "tags": [t.strip() for t in (tags or []) if t.strip()],
        "prompt": prompt.strip(),
        "created_at": now,
        "updated_at": now,
    }
    prompts.append(item)
    _save(prompts)
    return item


def update_prompt(
    prompt_id: str,
    name: Optional[str] = None,
    prompt: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Optional[dict]:
    prompts = _load()
    for i, p in enumerate(prompts):
        if p["id"] == prompt_id:
            if name is not None:
                p["name"] = name.strip()
            if prompt is not None:
                p["prompt"] = prompt.strip()
            if category is not None:
                p["category"] = category.strip()
            if tags is not None:
                p["tags"] = [t.strip() for t in tags if t.strip()]
            p["updated_at"] = _now()
            prompts[i] = p
            _save(prompts)
            return p
    return None


def delete_prompt(prompt_id: str) -> bool:
    prompts = _load()
    filtered = [p for p in prompts if p["id"] != prompt_id]
    if len(filtered) < len(prompts):
        _save(filtered)
        return True
    return False
