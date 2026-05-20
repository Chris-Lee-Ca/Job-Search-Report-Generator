"""
Job search pipeline orchestrator.

Usage:
    python fetch_jobs.py --setup          # one-time: log in via visible browser
    python fetch_jobs.py                  # run once
    python fetch_jobs.py --schedule 17:00 # run daily at HH:MM, stays alive
    python fetch_jobs.py --from-ids PATH  # resume detail fetch from saved IDs JSON
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CONFIG_FILE = "config.json"
OUTPUT_DIR = Path("output")
DEBUG_DIR = OUTPUT_DIR / "debug"
BROWSER_DATA_DIR = Path("browser_data")


def load_config() -> dict:
    with open(CONFIG_FILE, "r") as f:
        cfg = json.load(f)
    normalised = []
    for entry in cfg.get("search_urls", []):
        if isinstance(entry, str):
            normalised.append({"label": entry[:40], "url": entry, "remote_only": False})
        else:
            entry.setdefault("remote_only", False)
            normalised.append(entry)
    cfg["search_urls"] = normalised
    return cfg


def _build_provider(config: dict):
    """Instantiate the appropriate JobProvider based on configured search URLs."""
    urls = [e["url"] for e in config.get("search_urls", [])]
    if any("linkedin.com" in u for u in urls):
        from job_providers.linkedin_provider import LinkedInProvider
        return LinkedInProvider(
            output_dir=OUTPUT_DIR,
            debug_dir=DEBUG_DIR,
            browser_data_dir=BROWSER_DATA_DIR,
        )
    raise ValueError("No matching job provider for configured search URLs")


def _save_raw_jobs(jobs: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = OUTPUT_DIR / f"raw_jobs_{today}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    with_desc = sum(1 for j in jobs if j.get("description"))
    with_loc = sum(1 for j in jobs if j.get("location"))
    print(f"\n{'='*50}")
    print(f"Saved {len(jobs)} jobs → {out_path}")
    print(f"  With description : {with_desc}/{len(jobs)}")
    print(f"  With location    : {with_loc}/{len(jobs)}")
    print(f"{'='*50}")
    return out_path


def run_fetch():
    config = load_config()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting job fetch...")
    provider = _build_provider(config)
    jobs = provider.fetch_jobs(config["search_urls"])

    if not jobs:
        print("\nWARNING: 0 jobs fetched.")
        return

    out_path = _save_raw_jobs(jobs)
    print("\nRunning scorer...")
    from score_filter import run_score_filter
    run_score_filter(str(out_path))


def run_fetch_from_ids(ids_path: str):
    config = load_config()
    provider = _build_provider(config)
    jobs = provider.fetch_jobs_from_ids(ids_path)

    if not jobs:
        return

    out_path = _save_raw_jobs(jobs)
    print("\nRunning scorer...")
    from score_filter import run_score_filter
    run_score_filter(str(out_path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job search pipeline")
    parser.add_argument("--setup", action="store_true",
                        help="Open a visible browser to log into the job provider.")
    parser.add_argument("--schedule", metavar="HH:MM",
                        help="Run daily at this time. Keeps the process alive.")
    parser.add_argument("--from-ids", metavar="PATH",
                        help="Skip card-clicking; fetch details from a saved job_ids JSON file.")
    args = parser.parse_args()

    if args.setup:
        config = load_config()
        _build_provider(config).setup()
    elif getattr(args, "from_ids", None):
        run_fetch_from_ids(args.from_ids)
    elif args.schedule:
        import schedule as sched
        print(f"Scheduler started. Will run daily at {args.schedule}.")
        sched.every().day.at(args.schedule).do(run_fetch)
        run_fetch()
        while True:
            sched.run_pending()
            time.sleep(60)
    else:
        run_fetch()
