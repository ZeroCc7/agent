"""
Layer dependency linter for AI Photo Editor.

Enforces:
  Layer 0 (types/)  — no internal imports
  Layer 1 (core/)   — may import types/ only
  Layer 2 (api/)    — may import core/ + types/
  Layer 3 (main.py) — may import api/

Run: python scripts/lint-deps.py
"""

import ast
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent

LAYER_MAP = {
    "app/types": 0,
    "app/core": 1,
    "app/api": 2,
    "app/main": 3,
}

ALLOWED = {
    0: set(),
    1: {"app/types"},
    2: {"app/types", "app/core"},
    3: {"app/types", "app/core", "app/api"},
}


def module_to_layer_key(module: str) -> Optional[str]:
    """Map 'app.core.image_processor' → 'app/core'."""
    parts = module.split(".")
    for length in (3, 2):
        key = "/".join(parts[:length])
        if key in LAYER_MAP:
            return key
    return None


def file_layer_key(path: Path) -> Optional[str]:
    rel = path.relative_to(ROOT).as_posix().replace(".py", "")
    for key in LAYER_MAP:
        if rel == key or rel.startswith(key + "/"):
            return key
    return None


def check_file(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [f"{path}: SyntaxError — {e}"]

    src_key = file_layer_key(path)
    if src_key is None:
        return []
    src_layer = LAYER_MAP[src_key]
    allowed = ALLOWED[src_layer]

    errors = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
            if not module.startswith("app."):
                continue
            imported_key = module_to_layer_key(module)
            if imported_key and imported_key not in allowed and imported_key != src_key:
                imported_layer = LAYER_MAP[imported_key]
                errors.append(
                    f"\n  {path.relative_to(ROOT)}:{node.lineno} imports '{module}'\n"
                    f"  Layer {src_layer} ({src_key}) must NOT import layer {imported_layer} ({imported_key}).\n"
                    f"  Fix: move the logic to a higher layer or use dependency injection."
                )
    return errors


def main() -> int:
    py_files = [
        p for p in ROOT.rglob("*.py")
        if ".venv" not in p.parts and "node_modules" not in p.parts
        and "scripts" not in p.parts
    ]

    all_errors = []
    for f in sorted(py_files):
        all_errors.extend(check_file(f))

    if all_errors:
        print("LAYER DEPENDENCY VIOLATIONS:")
        for err in all_errors:
            print(err)
        print(f"\n{len(all_errors)} violation(s) found.")
        return 1

    print(f"OK — checked {len(py_files)} files, no layer violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
