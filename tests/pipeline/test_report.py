"""Unit tests for job_search.pipeline.report — no external services required."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest


SAMPLE_DAILY = """\
# Job Report — May 14, 2026

Fetched: 3 | Filtered out: 1 | Scored: 2

---

### [90] Stripe — Software Engineer · 🌐 Remote
Vancouver, BC · Full-time
✅ **Required matched:** Python, REST APIs

[View on LinkedIn](https://www.linkedin.com/jobs/view/111111111/)

- [x] Applied
- [ ] Hide

---

### [72] Shopify — Backend Developer · 🏢 Hybrid
Vancouver, BC · Full-time

[View on LinkedIn](https://www.linkedin.com/jobs/view/222222222/)

- [ ] Applied
- [x] Hide

---

### [60] Acme — DevOps Engineer · 🏛 Onsite

[View on LinkedIn](https://www.linkedin.com/jobs/view/333333333/)

- [x] Applied
- [ ] Hide

---

## Filtered Out

- **Google — Staff Engineer** — staff-level title
"""


def _applied_job(job_id, company, title, url):
    return {"job_id": job_id, "company": company, "title": title, "url": url, "score": "90"}


# ── extract_date_from_filename ────────────────────────────────────────────────

def test_extract_date_normal():
    from job_search.pipeline.report import extract_date_from_filename
    assert extract_date_from_filename("output/daily_jobs_2026-05-14.md") == "2026-05-14"

def test_extract_date_no_match_fallback_to_today():
    from job_search.pipeline.report import extract_date_from_filename
    result = extract_date_from_filename("output/some_file.md")
    assert result == datetime.now().strftime("%Y-%m-%d")


# ── parse_applied_jobs ────────────────────────────────────────────────────────

def test_parses_checked_jobs_only(tmp_path):
    from job_search.pipeline.report import parse_applied_jobs
    f = tmp_path / "daily.md"
    f.write_text(SAMPLE_DAILY)
    result = parse_applied_jobs(str(f))
    assert len(result) == 2
    companies = {j["company"] for j in result}
    assert companies == {"Stripe", "Acme"}

def test_unchecked_job_not_parsed(tmp_path):
    from job_search.pipeline.report import parse_applied_jobs
    f = tmp_path / "daily.md"
    f.write_text(SAMPLE_DAILY)
    result = parse_applied_jobs(str(f))
    assert not any(j["company"] == "Shopify" for j in result)

def test_extracts_url_correctly(tmp_path):
    from job_search.pipeline.report import parse_applied_jobs
    f = tmp_path / "daily.md"
    f.write_text(SAMPLE_DAILY)
    result = parse_applied_jobs(str(f))
    stripe = next(j for j in result if j["company"] == "Stripe")
    assert stripe["url"] == "https://www.linkedin.com/jobs/view/111111111/"

def test_extracts_job_id_from_url(tmp_path):
    from job_search.pipeline.report import parse_applied_jobs
    f = tmp_path / "daily.md"
    f.write_text(SAMPLE_DAILY)
    result = parse_applied_jobs(str(f))
    stripe = next(j for j in result if j["company"] == "Stripe")
    assert stripe["job_id"] == "111111111"

def test_no_applied_returns_empty(tmp_path):
    from job_search.pipeline.report import parse_applied_jobs
    content = SAMPLE_DAILY.replace("- [x] Applied", "- [ ] Applied")
    f = tmp_path / "daily.md"
    f.write_text(content)
    assert parse_applied_jobs(str(f)) == []


# ── generate_report ───────────────────────────────────────────────────────────

def test_report_contains_all_applied_jobs(tmp_path):
    from job_search.pipeline.report import generate_report
    jobs = [
        _applied_job("111", "Stripe", "Software Engineer", "https://linkedin.com/jobs/view/111/"),
        _applied_job("222", "Shopify", "Backend Dev", "https://linkedin.com/jobs/view/222/"),
    ]
    out = tmp_path / "report.md"
    generate_report(jobs, "2026-05-14", append=False, out_path=out)
    content = out.read_text()
    assert "Stripe" in content
    assert "Shopify" in content
    assert "2026-05-14" in content

def test_report_markdown_table_structure(tmp_path):
    from job_search.pipeline.report import generate_report
    jobs = [_applied_job("111", "Stripe", "SWE", "https://linkedin.com/jobs/view/111/")]
    out = tmp_path / "report.md"
    generate_report(jobs, "2026-05-14", append=False, out_path=out)
    content = out.read_text()
    assert "| # |" in content
    assert "| Date Applied |" in content

def test_append_mode_adds_to_existing(tmp_path):
    from job_search.pipeline.report import generate_report
    jobs1 = [_applied_job("111", "Stripe", "SWE", "https://linkedin.com/jobs/view/111/")]
    jobs2 = [_applied_job("222", "Shopify", "Dev", "https://linkedin.com/jobs/view/222/")]
    out = tmp_path / "report.md"
    generate_report(jobs1, "2026-05-13", append=False, out_path=out)
    generate_report(jobs2, "2026-05-14", append=True, out_path=out)
    content = out.read_text()
    assert "Stripe" in content
    assert "Shopify" in content


# ── parse_hidden_jobs ─────────────────────────────────────────────────────────

def test_parses_hidden_jobs_only(tmp_path):
    from job_search.pipeline.report import parse_hidden_jobs
    f = tmp_path / "daily.md"
    f.write_text(SAMPLE_DAILY)
    result = parse_hidden_jobs(str(f))
    assert len(result) == 1
    assert result[0]["company"] == "Shopify"

def test_applied_job_not_in_hidden(tmp_path):
    from job_search.pipeline.report import parse_hidden_jobs
    f = tmp_path / "daily.md"
    f.write_text(SAMPLE_DAILY)
    result = parse_hidden_jobs(str(f))
    assert not any(j["company"] == "Stripe" for j in result)
    assert not any(j["company"] == "Acme" for j in result)


# ── run_report hide handling ──────────────────────────────────────────────────

def test_hide_checkbox_sets_skip_in_seen_jobs(tmp_path):
    from job_search.pipeline.report import run_report
    f = tmp_path / "daily_jobs_2026-05-14.md"
    f.write_text(SAMPLE_DAILY)

    seen = {}
    saved = {}

    def fake_load():
        return seen

    def fake_save(data):
        saved.update(data)

    with (
        patch("job_search.pipeline.report.load_seen_jobs", fake_load),
        patch("job_search.pipeline.report.save_seen_jobs", fake_save),
        patch("job_search.pipeline.report.update_applied"),
        patch("job_search.pipeline.report.backfill_from_files"),
        patch("job_search.pipeline.report.generate_trend_chart"),
        patch("job_search.pipeline.report.load_daily_stats", return_value={}),
    ):
        run_report(str(f))

    assert saved.get("222222222", {}).get("skip") is True

def test_hide_only_no_report_generated(tmp_path):
    """When only Hide is checked (no Applied), no EI report file is written."""
    from job_search.pipeline.report import run_report
    hide_only = SAMPLE_DAILY.replace("- [x] Applied", "- [ ] Applied")
    f = tmp_path / "daily_jobs_2026-05-14.md"
    f.write_text(hide_only)

    saved = {}

    with (
        patch("job_search.pipeline.report.load_seen_jobs", return_value={}),
        patch("job_search.pipeline.report.save_seen_jobs", lambda d: saved.update(d)),
        patch("job_search.pipeline.report.update_applied"),
        patch("job_search.pipeline.report.backfill_from_files"),
        patch("job_search.pipeline.report.generate_trend_chart"),
        patch("job_search.pipeline.report.load_daily_stats", return_value={}),
    ):
        run_report(str(f))

    assert saved.get("222222222", {}).get("skip") is True
    assert not any((tmp_path / "reports").glob("*.md")) if (tmp_path / "reports").exists() else True
