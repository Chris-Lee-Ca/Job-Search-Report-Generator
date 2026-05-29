"""Re-score jobs that errored during a previous run.

Fail-fast: stops on the first new error and saves the raw API response
to output/debug/ so the bad response can be inspected.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OUTPUT_DIR = Path("output")
RAW_DIR = OUTPUT_DIR / "raw"
DEBUG_DIR = OUTPUT_DIR / "debug"


def _parse_error_job_ids(daily_path: Path) -> list[str]:
    """Return LinkedIn job IDs listed in the ## Errors section only.

    Stops at the next ## heading so that IDs in ## Filtered Out are not included.
    """
    content = daily_path.read_text(encoding="utf-8")
    m = re.search(r"## Errors.*?(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        return []
    return re.findall(r"linkedin\.com/jobs/view/(\d+)/", m.group(0))


def _infer_raw_path(daily_path: Path) -> Path:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", daily_path.name)
    if not m:
        raise ValueError(f"Cannot infer date from filename: {daily_path.name}")
    return RAW_DIR / f"raw_jobs_{m.group(1)}.json"


def _patch_daily_file(
    daily_path: Path,
    scored_jobs: list,   # [(job, analysis, previously_applied), ...]
    filtered_jobs: list, # [{"company", "title", "url", "reason"}, ...]
) -> None:
    from job_search.pipeline.score import (
        _categorize_filter_reason,
        _format_job_section,
    )

    content = daily_path.read_text(encoding="utf-8")

    # Remove the entire ## Errors section
    content = re.sub(r"\n## Errors.*?(?=\n## |\Z)", "", content, flags=re.DOTALL)

    # Update the header stats line
    def _bump(m: re.Match) -> str:
        return (
            f"Fetched: {m.group(1)} | "
            f"Filtered out: {int(m.group(2)) + len(filtered_jobs)} | "
            f"Scored: {int(m.group(3)) + len(scored_jobs)}"
        )
    content = re.sub(
        r"Fetched: (\d+) \| Filtered out: (\d+) \| Scored: (\d+)",
        _bump,
        content,
    )

    # Insert newly scored job blocks before ## Filtered Out (or at the end)
    if scored_jobs:
        new_blocks = "\n\n---\n\n".join(
            _format_job_section(job, analysis, prev)
            for job, analysis, prev in scored_jobs
        )
        insert_match = re.search(r"\n## Filtered Out", content)
        if insert_match:
            pos = insert_match.start()
            content = content[:pos] + "\n\n---\n\n" + new_blocks + content[pos:]
        else:
            content = content.rstrip() + "\n\n---\n\n" + new_blocks + "\n\n---\n"

    # Append newly filtered jobs into the ## Filtered Out section
    if filtered_jobs:
        filtered_match = re.search(r"\n## Filtered Out\n", content)
        if filtered_match:
            lines = []
            for fj in filtered_jobs:
                cat, note = _categorize_filter_reason(fj["reason"])
                company = fj.get("company", "")
                title = fj.get("title", "")
                name = f"{company} — {title}" if company else title
                if note:
                    name += f" *({note})*"
                url = fj.get("url", "")
                label = f"[{name}]({url})" if url else name
                lines.append(f"- {label} *(retried)*")
            insert_pos = filtered_match.end()
            content = content[:insert_pos] + "\n".join(lines) + "\n\n" + content[insert_pos:]

    daily_path.write_text(content, encoding="utf-8")


def run_retry_errors(daily_path_str: str) -> None:
    from job_search.config import load_config, load_resume, load_seen_jobs
    from job_search.pipeline.score import (
        build_provider,
        _effective_score,
        _filter_false_missing,
    )

    daily_path = Path(daily_path_str)
    if not daily_path.exists():
        print(f"Error: {daily_path} not found.", file=sys.stderr)
        sys.exit(1)

    error_ids = _parse_error_job_ids(daily_path)
    if not error_ids:
        print("No error jobs found in the daily file.")
        return

    print(f"Found {len(error_ids)} error job(s) to retry.")

    raw_path = _infer_raw_path(daily_path)
    if not raw_path.exists():
        print(f"Error: raw jobs file not found: {raw_path}", file=sys.stderr)
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        all_jobs = json.load(f)

    id_set = set(error_ids)
    jobs_to_retry = [j for j in all_jobs if str(j.get("id", "")) in id_set]

    if not jobs_to_retry:
        print("Could not match any error job IDs to the raw jobs file.")
        sys.exit(1)

    if len(jobs_to_retry) < len(error_ids):
        found = {str(j.get("id", "")) for j in jobs_to_retry}
        missing = id_set - found
        print(f"Warning: {len(missing)} job ID(s) not found in raw data: {', '.join(missing)}")

    config = load_config()
    scoring = config.get("scoring", {})
    remote_bonus = scoring.get("remote_score_bonus", 5)
    max_years = scoring.get("max_years", 6)
    filter_criteria = [
        c.format(max_years=max_years) for c in config.get("hard_filter_criteria", [])
    ]

    resume = load_resume()
    seen = load_seen_jobs()
    provider = build_provider(config)

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    scored_jobs: list = []
    filtered_jobs: list = []

    for i, job in enumerate(jobs_to_retry, 1):
        job_id = str(job.get("id", "unknown"))
        print(
            f"  [{i}/{len(jobs_to_retry)}] {job.get('company', '?')} — {job.get('title', '?')}",
            end=" ... ",
            flush=True,
        )

        try:
            analysis = provider.analyze_job(
                resume=resume,
                job_title=job.get("title", ""),
                job_description=job.get("description", ""),
                filter_criteria=filter_criteria,
            )
        except Exception as e:
            raw = getattr(provider, "_last_raw", None)
            debug_path = DEBUG_DIR / f"retry_raw_{job_id}.txt"
            if raw:
                debug_path.write_text(raw, encoding="utf-8")
                print(f"\n  ERROR: {e}")
                print(f"  Raw response saved → {debug_path}")
            else:
                print(f"\n  ERROR: {e}")
                print("  (no raw response captured — error may have occurred before the API call)")
            print("\nStopped. Fix the issue then retry.")
            sys.exit(1)

        analysis.unmatched_required_skills = _filter_false_missing(
            getattr(analysis, "unmatched_required_skills", []), resume
        )

        min_yrs = getattr(analysis, "min_years_required", 0)
        if not analysis.should_filter and min_yrs >= max_years:
            analysis.should_filter = True
            analysis.filter_reason = f"Requires {min_yrs}+ years experience (code-enforced)"

        previously_applied = seen.get(job_id, {}).get("applied", False)

        if analysis.should_filter:
            print(f"FILTERED ({analysis.filter_reason})")
            filtered_jobs.append({
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "url": job.get("url", ""),
                "reason": analysis.filter_reason or "filtered",
            })
        else:
            analysis.score = _effective_score(analysis.score, analysis.work_mode, remote_bonus)
            print(f"score={analysis.score} ({analysis.work_mode})")
            scored_jobs.append((job, analysis, previously_applied))

    _patch_daily_file(daily_path, scored_jobs, filtered_jobs)
    print(f"\n✓ Patched {daily_path}")
    print(f"  {len(scored_jobs)} newly scored | {len(filtered_jobs)} newly filtered")
