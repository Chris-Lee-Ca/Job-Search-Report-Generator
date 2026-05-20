#!/usr/bin/env python3
"""
Job search pipeline CLI.

Commands:
    python main.py fetch              # Scrape LinkedIn + score jobs
    python main.py fetch --setup      # One-time LinkedIn login
    python main.py fetch --schedule 17:00
    python main.py fetch --from-ids output/raw/job_ids_2026-05-20.json
    python main.py score              # Re-score today's raw jobs
    python main.py score output/raw/raw_jobs_2026-05-20.json
    python main.py report output/daily_jobs_2026-05-20.md
    python main.py report output/daily_jobs_2026-05-20.md --append
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv(Path("config") / ".env")


@click.group()
def cli():
    """Job search pipeline — fetch, score, and report."""


@cli.command()
@click.option("--setup", is_flag=True, help="Open a visible browser to log into LinkedIn (one-time).")
@click.option("--schedule", metavar="HH:MM", default=None, help="Run daily at this time; keeps process alive.")
@click.option("--from-ids", "from_ids", metavar="PATH", default=None,
              help="Skip card-clicking; fetch details from a saved job_ids JSON file.")
def fetch(setup: bool, schedule: str | None, from_ids: str | None):
    """Scrape LinkedIn job listings and run the scorer."""
    from job_search.pipeline.fetch import run_fetch, run_setup, run_fetch_from_ids

    if setup:
        run_setup()
    elif from_ids:
        run_fetch_from_ids(from_ids)
    elif schedule:
        import schedule as sched
        print(f"Scheduler started. Will run daily at {schedule}.")
        sched.every().day.at(schedule).do(run_fetch)
        run_fetch()
        while True:
            sched.run_pending()
            time.sleep(60)
    else:
        run_fetch()


@cli.command()
@click.argument("raw_path", required=False, default=None,
                metavar="[RAW_PATH]")
def score(raw_path: str | None):
    """Score and filter jobs from a raw JSON file (defaults to today's file)."""
    from job_search.pipeline.score import run_score_filter
    run_score_filter(raw_path)


@cli.command()
@click.argument("daily_file")
@click.option("--append", is_flag=True, help="Append to a monthly report instead of creating a new file.")
def report(daily_file: str, append: bool):
    """Generate an EI application report from a checked daily job file."""
    from job_search.pipeline.report import run_report
    try:
        run_report(daily_file, append=append)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
