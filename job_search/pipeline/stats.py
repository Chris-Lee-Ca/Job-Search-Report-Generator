"""Track and persist daily scored/applied counts for trend analysis."""

from __future__ import annotations

import json
import re
from pathlib import Path

STATS_PATH = Path("data/daily_stats.json")
OUTPUT_DIR = Path("output")
SEEN_JOBS_PATH = Path("data/seen_jobs.json")


def load_daily_stats() -> dict[str, dict]:
    if STATS_PATH.exists():
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_daily_stats(stats: dict[str, dict]) -> None:
    STATS_PATH.parent.mkdir(exist_ok=True)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=True)


def update_scored(date: str, scored: int) -> None:
    stats = load_daily_stats()
    entry = stats.setdefault(date, {})
    entry["scored"] = scored
    save_daily_stats(stats)


def update_applied(date: str, applied: int) -> None:
    stats = load_daily_stats()
    entry = stats.setdefault(date, {})
    entry["applied"] = applied
    save_daily_stats(stats)


def _parse_scored_from_daily_file(path: Path) -> int | None:
    """Extract the Scored count from the header line of a daily_jobs file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.search(r"Scored:\s*(\d+)", line)
                if m:
                    return int(m.group(1))
    except OSError:
        pass
    return None


def _count_applied_from_seen_jobs() -> dict[str, int]:
    """Count applied jobs per applied_date from seen_jobs.json."""
    if not SEEN_JOBS_PATH.exists():
        return {}
    with open(SEEN_JOBS_PATH, "r", encoding="utf-8") as f:
        seen = json.load(f)
    counts: dict[str, int] = {}
    for entry in seen.values():
        if entry.get("applied") and entry.get("applied_date"):
            d = entry["applied_date"]
            counts[d] = counts.get(d, 0) + 1
    return counts


def backfill_from_files() -> None:
    """
    Seed daily_stats.json from existing output files.
    Only fills in missing entries — never overwrites data already recorded.
    """
    stats = load_daily_stats()

    # scored counts from daily_jobs_*.md headers
    for daily_file in sorted(OUTPUT_DIR.glob("daily_jobs_*.md")):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", daily_file.name)
        if not m:
            continue
        date = m.group(1)
        if date not in stats or "scored" not in stats[date]:
            scored = _parse_scored_from_daily_file(daily_file)
            if scored is not None:
                stats.setdefault(date, {})["scored"] = scored

    # applied counts from seen_jobs.json
    applied_by_date = _count_applied_from_seen_jobs()
    for date, count in applied_by_date.items():
        if date not in stats or "applied" not in stats[date]:
            stats.setdefault(date, {})["applied"] = count

    save_daily_stats(stats)
