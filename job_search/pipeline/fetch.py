"""Job fetch pipeline — scrape LinkedIn and invoke the scorer."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from job_search.config import load_config

OUTPUT_DIR = Path("output")
RAW_DIR = OUTPUT_DIR / "raw"
DEBUG_DIR = OUTPUT_DIR / "debug"
BROWSER_DATA_DIR = Path("browser_data")


def _build_provider(config: dict):
    """Instantiate the appropriate JobProvider based on configured search URLs."""
    urls = [e["url"] for e in config.get("search_urls", [])]
    if any("linkedin.com" in u for u in urls):
        from job_search.providers.scrapers.linkedin import LinkedInProvider
        return LinkedInProvider(
            output_dir=OUTPUT_DIR,
            debug_dir=DEBUG_DIR,
            browser_data_dir=BROWSER_DATA_DIR,
            linkedin_cfg=config.get("linkedin", {}),
        )
    raise ValueError("No matching job provider for configured search URLs")


def _save_raw_jobs(jobs: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = RAW_DIR / f"raw_jobs_{today}.json"
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
    from job_search.pipeline.score import run_score_filter
    run_score_filter(str(out_path))


def run_setup():
    config = load_config()
    _build_provider(config).setup()


def run_fetch_from_ids(ids_path: str):
    config = load_config()
    provider = _build_provider(config)
    jobs = provider.fetch_jobs_from_ids(ids_path)

    if not jobs:
        return

    out_path = _save_raw_jobs(jobs)
    print("\nRunning scorer...")
    from job_search.pipeline.score import run_score_filter
    run_score_filter(str(out_path))
