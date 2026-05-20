"""Shared config/data helpers used across the entire pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent
CONFIG_FILE = _ROOT / "config" / "config.yaml"
RESUME_FILE = _ROOT / "config" / "resume.md"
DATA_DIR = _ROOT / "data"
SEEN_JOBS_FILE = DATA_DIR / "seen_jobs.json"


def load_config(path: Path | None = None) -> dict:
    """Load config/config.yaml and normalise search_urls entries."""
    with open(path or CONFIG_FILE, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    normalised = []
    for entry in cfg.get("search_urls", []):
        if isinstance(entry, str):
            normalised.append({"label": entry[:40], "url": entry, "remote_only": False})
        else:
            entry.setdefault("remote_only", False)
            normalised.append(entry)
    cfg["search_urls"] = normalised
    return cfg


def load_resume(path: Path | None = None) -> str:
    with open(path or RESUME_FILE, encoding="utf-8") as f:
        return f.read()


def load_seen_jobs(path: Path | None = None) -> dict:
    p = path or SEEN_JOBS_FILE
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen_jobs(data: dict, path: Path | None = None) -> None:
    p = path or SEEN_JOBS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
