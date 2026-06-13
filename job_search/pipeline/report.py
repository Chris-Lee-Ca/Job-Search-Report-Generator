"""Generate an EI-compatible job application report from a checked daily job file."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from job_search.config import load_seen_jobs, save_seen_jobs
from job_search.pipeline.stats import backfill_from_files, load_daily_stats, update_applied
from job_search.pipeline.chart import generate_trend_chart, CHART_PATH

REPORTS_DIR = Path("reports")


def extract_date_from_filename(path: str) -> str:
    """Extract YYYY-MM-DD from filename like daily_jobs_2026-05-13.md."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def _parse_job_sections(daily_file: str) -> list[dict]:
    """Split the daily file into per-job section dicts with all parsed fields."""
    with open(daily_file, "r", encoding="utf-8") as f:
        content = f.read()

    sections = re.split(r"(?=^### \[)", content, flags=re.MULTILINE)
    parsed = []

    for section in sections:
        heading_match = re.match(
            r"### \[(\d+)\]\s+(?:(.+?)\s+)?—\s+(.+?)(?:\s+·|$)", section
        )
        if not heading_match:
            continue

        score = heading_match.group(1)
        company = (heading_match.group(2) or "").strip()
        title = heading_match.group(3).strip()

        url_match = re.search(r"\[View on LinkedIn\]\((https?://[^\)]+)\)", section)
        url = url_match.group(1) if url_match else ""

        job_id_match = re.search(r"/jobs/view/(\d+)", url)
        job_id = job_id_match.group(1) if job_id_match else None

        applied = "- [x] Applied" in section or "- [X] Applied" in section
        hidden = "- [x] Hide" in section or "- [X] Hide" in section

        parsed.append({
            "job_id": job_id,
            "company": company,
            "title": title,
            "url": url,
            "score": score,
            "applied": applied,
            "hidden": hidden,
        })

    return parsed


def parse_applied_jobs(daily_file: str) -> list[dict]:
    """Return jobs where the user checked [x] Applied."""
    return [j for j in _parse_job_sections(daily_file) if j["applied"]]


def parse_hidden_jobs(daily_file: str) -> list[dict]:
    """Return jobs where the user checked [x] Hide."""
    return [j for j in _parse_job_sections(daily_file) if j["hidden"]]


def generate_report(applied_jobs: list[dict], date: str, append: bool, out_path: Path):
    display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")

    table_rows = []
    for i, job in enumerate(applied_jobs, 1):
        table_rows.append(
            f"| {i} | {date} | {job['company']} | {job['title']} | {job['url']} |"
        )

    report_block = (
        f"# Job Applications — {display_date}\n\n"
        "| # | Date Applied | Company | Job Title | URL |\n"
        "|---|---|---|---|---|\n"
        + "\n".join(table_rows)
        + "\n"
    )

    REPORTS_DIR.mkdir(exist_ok=True)

    if append and out_path.exists():
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n{report_block}")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report_block)


def run_report(daily_file: str, append: bool = False):
    daily_path = Path(daily_file)
    if not daily_path.exists():
        raise FileNotFoundError(f"File not found: {daily_file}")

    date = extract_date_from_filename(daily_file)
    applied_jobs = parse_applied_jobs(daily_file)
    hidden_jobs = parse_hidden_jobs(daily_file)

    if not applied_jobs and not hidden_jobs:
        print("No checked jobs found. Mark jobs with '- [x] Applied' or '- [x] Hide' in the daily file first.")
        return

    seen = load_seen_jobs()

    if applied_jobs:
        print(f"Found {len(applied_jobs)} applied job(s):")
        for job in applied_jobs:
            print(f"  · {job['company']} — {job['title']}")
        for job in applied_jobs:
            job_id = job.get("job_id")
            if job_id:
                if job_id in seen:
                    seen[job_id]["applied"] = True
                    seen[job_id]["applied_date"] = date
                else:
                    seen[job_id] = {
                        "first_seen": date,
                        "title": job["title"],
                        "company": job["company"],
                        "applied": True,
                        "applied_date": date,
                        "skip": False,
                    }

    if hidden_jobs:
        print(f"Hiding {len(hidden_jobs)} job(s) — won't appear in future runs:")
        for job in hidden_jobs:
            print(f"  · {job['company']} — {job['title']}")
        for job in hidden_jobs:
            job_id = job.get("job_id")
            if job_id:
                if job_id in seen:
                    seen[job_id]["skip"] = True
                else:
                    seen[job_id] = {
                        "first_seen": date,
                        "title": job["title"],
                        "company": job["company"],
                        "applied": False,
                        "applied_date": None,
                        "skip": True,
                    }

    save_seen_jobs(seen)

    print("seen_jobs.json updated.")

    if not applied_jobs:
        return

    if append:
        year_month = date[:7]
        out_path = REPORTS_DIR / f"applied_{year_month}.md"
    else:
        out_path = REPORTS_DIR / f"applied_{date}.md"

    generate_report(applied_jobs, date, append, out_path)

    total_applied = sum(1 for v in seen.values() if v.get("applied"))

    # Update daily stats and regenerate the trend chart
    update_applied(date, len(applied_jobs))
    backfill_from_files()
    generate_trend_chart(load_daily_stats())

    print(f"\nReport saved → {out_path}")
    print(f"Trend chart updated → {CHART_PATH}")
    print(f"\nTotal jobs applied since day 1: {total_applied}")
