"""
Generate an EI-compatible job application report from a checked daily job file.

Usage:
    python generate_report.py output/daily_jobs_2026-05-13.md
    python generate_report.py output/daily_jobs_2026-05-13.md --append
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")
SEEN_JOBS_FILE = DATA_DIR / "seen_jobs.json"
REPORTS_DIR = Path("reports")


def load_seen_jobs() -> dict:
    if SEEN_JOBS_FILE.exists():
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen_jobs(seen: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def extract_date_from_filename(path: str) -> str:
    """Extract YYYY-MM-DD from filename like daily_jobs_2026-05-13.md"""
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

    # Split into job sections by "### [" heading
    sections = re.split(r"(?=^### \[)", content, flags=re.MULTILINE)

    applied = []

    for section in sections:
        if "- [x] Applied" not in section and "- [X] Applied" not in section:
            continue

        # Extract score + company + title from heading.
        # Company is optional — jobs with no company produce "### [93] — Title · emoji"
        heading_match = re.match(
            r"### \[(\d+)\]\s+(?:(.+?)\s+)?—\s+(.+?)(?:\s+·|$)", section
        )
        if not heading_match:
            continue

        score = heading_match.group(1)
        company = (heading_match.group(2) or "").strip()
        title = heading_match.group(3).strip()

        # Extract URL
        url_match = re.search(r"\[View on LinkedIn\]\((https?://[^\)]+)\)", section)
        url = url_match.group(1) if url_match else ""

        # Extract job ID from URL
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


def main():
    parser = argparse.ArgumentParser(description="Generate EI job application report")
    parser.add_argument("daily_file", help="Path to the daily job file (e.g. output/daily_jobs_2026-05-13.md)")
    parser.add_argument("--append", action="store_true", help="Append to monthly report instead of creating a new file")
    args = parser.parse_args()

    daily_path = Path(args.daily_file)
    if not daily_path.exists():
        print(f"File not found: {args.daily_file}")
        sys.exit(1)

    date = extract_date_from_filename(args.daily_file)
    applied_jobs = parse_applied_jobs(args.daily_file)

    if not applied_jobs:
        print("No checked jobs found. Mark jobs with '- [x] Applied' in the daily file first.")
        sys.exit(0)

    print(f"Found {len(applied_jobs)} applied job(s):")
    for job in applied_jobs:
        print(f"  · {job['company']} — {job['title']}")

    # Update seen_jobs.json
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

    # Determine output file
    if args.append:
        year_month = date[:7]  # YYYY-MM
        out_path = REPORTS_DIR / f"applied_{year_month}.md"
    else:
        out_path = REPORTS_DIR / f"applied_{date}.md"

    generate_report(applied_jobs, date, args.append, out_path)

    print(f"\nReport saved → {out_path}")
    print("seen_jobs.json updated.")


if __name__ == "__main__":
    main()
