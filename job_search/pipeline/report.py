"""Generate an EI-compatible job application report from a checked daily job file."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from job_search.config import load_seen_jobs, save_seen_jobs

REPORTS_DIR = Path("reports")


def extract_date_from_filename(path: str) -> str:
    """Extract YYYY-MM-DD from filename like daily_jobs_2026-05-13.md."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", Path(path).name)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def parse_applied_jobs(daily_file: str) -> list[dict]:
    """
    Parse the daily job file and return jobs where the user checked [x] Applied.

    Job section structure:
        ### [95] Company — Title · emoji WorkMode
        ...
        [View on LinkedIn](URL)
        - [x] Applied        ← we look for this
    """
    with open(daily_file, "r", encoding="utf-8") as f:
        content = f.read()

    sections = re.split(r"(?=^### \[)", content, flags=re.MULTILINE)

    applied = []

    for section in sections:
        if "- [x] Applied" not in section and "- [X] Applied" not in section:
            continue

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

        applied.append({
            "job_id": job_id,
            "company": company,
            "title": title,
            "url": url,
            "score": score,
        })

    return applied


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

    if not applied_jobs:
        print("No checked jobs found. Mark jobs with '- [x] Applied' in the daily file first.")
        return

    print(f"Found {len(applied_jobs)} applied job(s):")
    for job in applied_jobs:
        print(f"  · {job['company']} — {job['title']}")

    seen = load_seen_jobs()
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
                }
    save_seen_jobs(seen)

    if append:
        year_month = date[:7]
        out_path = REPORTS_DIR / f"applied_{year_month}.md"
    else:
        out_path = REPORTS_DIR / f"applied_{date}.md"

    generate_report(applied_jobs, date, append, out_path)

    total_applied = sum(1 for v in seen.values() if v.get("applied"))

    print(f"\nReport saved → {out_path}")
    print("seen_jobs.json updated.")
    print(f"\nTotal jobs applied since day 1: {total_applied}")
