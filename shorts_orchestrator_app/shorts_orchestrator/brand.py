from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shorts_orchestrator.settings import BRAND_BIBLES_DIR, LEARNING_DIR


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def brand_bible_path(account: str) -> Path:
    return BRAND_BIBLES_DIR / f"{account}.brand_bible.yaml"


def load_brand_bible(account: str) -> dict[str, Any]:
    return _load_yaml(brand_bible_path(account))


def learning_file(account: str) -> Path:
    return LEARNING_DIR / f"{account}_lessons.md"


def load_learning_notes(account: str) -> str:
    path = learning_file(account)
    if not path.exists():
        return "No analytics learning notes yet. Use conservative channel defaults."
    return path.read_text(encoding="utf-8")


def append_learning_notes(account: str, notes: str) -> Path:
    path = learning_file(account)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write("\n\n---\n")
        f.write(notes.strip() + "\n")
    return path
