"""Tests for score_filter.py — no LinkedIn or LLM required."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from providers.base import JobAnalysis


def _analysis(**overrides) -> JobAnalysis:
    defaults = dict(
        should_filter=False, filter_reason=None,
        score=70, score_reasoning="Good match.",
        matched_required_skills=["Python"], matched_nice_skills=["Docker"],
        required_skills=["Python"], nice_to_have_skills=["Docker"],
        seniority_required="Mid-level (2-4 yrs)",
        work_mode="Remote", industry="Tech",
        primary_tech_mismatch=False, mismatch_reason=None,
    )
    defaults.update(overrides)
    return JobAnalysis(**defaults)


class _MockProvider:
    def __init__(self, analyses: list):
        self._queue = iter(analyses)

    def analyze_job(self, **_):
        return next(self._queue)


# ── _effective_score ────────────────────────────────────────────────────────

def test_remote_bonus_applied():
    from score_filter import _effective_score
    assert _effective_score(70, "Remote", 5) == 75

def test_hybrid_gets_half_bonus():
    from score_filter import _effective_score
    assert _effective_score(70, "Hybrid", 5) == 72

def test_onsite_no_bonus():
    from score_filter import _effective_score
    assert _effective_score(70, "Onsite", 5) == 70

def test_score_capped_at_100():
    from score_filter import _effective_score
    assert _effective_score(98, "Remote", 5) == 100
    assert _effective_score(100, "Remote", 10) == 100


# ── _format_job_section ─────────────────────────────────────────────────────

def _sample_job(**overrides):
    base = dict(
        id="123456", title="Software Engineer", company="Acme Corp",
        location="Vancouver, BC", employment_type="Full-time",
        url="https://www.linkedin.com/jobs/view/123456/",
        description="We need a Python engineer to build things.",
    )
    base.update(overrides)
    return base

def test_section_contains_score_company_title():
    from score_filter import _format_job_section
    out = _format_job_section(_sample_job(), _analysis(score=85), previously_applied=False)
    assert "[85]" in out
    assert "Acme Corp" in out
    assert "Software Engineer" in out

def test_section_contains_linkedin_url():
    from score_filter import _format_job_section
    out = _format_job_section(_sample_job(), _analysis(), previously_applied=False)
    assert "https://www.linkedin.com/jobs/view/123456/" in out

def test_section_has_unchecked_applied_box():
    from score_filter import _format_job_section
    out = _format_job_section(_sample_job(), _analysis(), previously_applied=False)
    assert "- [ ] Applied" in out

def test_previously_applied_marker():
    from score_filter import _format_job_section
    out = _format_job_section(_sample_job(), _analysis(), previously_applied=True)
    assert "PREVIOUSLY APPLIED" in out

def test_section_shows_matched_skills():
    from score_filter import _format_job_section
    out = _format_job_section(
        _sample_job(),
        _analysis(matched_required_skills=["Python", "Go"], matched_nice_skills=["Kubernetes"]),
        previously_applied=False,
    )
    assert "Python" in out
    assert "Go" in out
    assert "Kubernetes" in out

def test_section_description_excerpt_truncated():
    from score_filter import _format_job_section
    long_desc = "x" * 400
    out = _format_job_section(_sample_job(description=long_desc), _analysis(), previously_applied=False)
    assert "..." in out


# ── run_score_filter (integration) ──────────────────────────────────────────

def _run_with_mock(jobs: list, analyses: list, tmp_dir: str) -> str:
    """Run score_filter against mock jobs and return the output markdown content."""
    raw_path = os.path.join(tmp_dir, "raw_jobs_2026-05-14.json")
    with open(raw_path, "w") as f:
        json.dump(jobs, f)

    provider = _MockProvider(analyses)
    seen_path = Path(tmp_dir) / "seen.json"
    out_dir = Path(tmp_dir)

    with patch("score_filter.build_provider", return_value=provider), \
         patch("score_filter.SEEN_JOBS_FILE", seen_path), \
         patch("score_filter.OUTPUT_DIR", out_dir), \
         patch("score_filter.load_resume", return_value="Mock resume content"):
        from score_filter import run_score_filter
        run_score_filter(raw_path)

    out_file = out_dir / "daily_jobs_2026-05-14.md"
    assert out_file.exists(), "Output markdown was not created"
    return out_file.read_text()

def test_scored_job_appears_in_output():
    jobs = [{"id": "aaa", "title": "Backend Dev", "company": "Beta Inc",
              "location": "Vancouver", "url": "https://linkedin.com/jobs/view/aaa/", "description": "Python role"}]
    with tempfile.TemporaryDirectory() as tmp:
        content = _run_with_mock(jobs, [_analysis(score=80, work_mode="Remote")], tmp)
    assert "Beta Inc" in content
    assert "Backend Dev" in content

def test_filtered_job_not_in_main_list():
    jobs = [
        {"id": "aaa", "title": "Intern Dev", "company": "Co1",
         "location": "Vancouver", "url": "https://linkedin.com/jobs/view/aaa/", "description": "Internship"},
        {"id": "bbb", "title": "Software Engineer", "company": "Co2",
         "location": "Vancouver", "url": "https://linkedin.com/jobs/view/bbb/", "description": "Full-time"},
    ]
    analyses = [
        _analysis(should_filter=True, filter_reason="Internship role"),
        _analysis(score=75, work_mode="Remote"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        content = _run_with_mock(jobs, analyses, tmp)

    main, _, filtered = content.partition("## Filtered Out")
    assert "Co1" not in main
    assert "Co2" in main
    assert "Co1" in filtered

def test_jobs_sorted_by_score_descending():
    jobs = [
        {"id": "low", "title": "Dev A", "company": "A", "location": "",
         "url": "https://linkedin.com/jobs/view/low/", "description": ""},
        {"id": "high", "title": "Dev B", "company": "B", "location": "",
         "url": "https://linkedin.com/jobs/view/high/", "description": ""},
    ]
    analyses = [_analysis(score=40, work_mode="Onsite"), _analysis(score=90, work_mode="Onsite")]
    with tempfile.TemporaryDirectory() as tmp:
        content = _run_with_mock(jobs, analyses, tmp)

    assert content.index("[90]") < content.index("[40]")

def test_new_jobs_written_to_seen_jobs():
    jobs = [{"id": "xyz", "title": "Dev", "company": "Org", "location": "",
              "url": "https://linkedin.com/jobs/view/xyz/", "description": ""}]
    with tempfile.TemporaryDirectory() as tmp:
        _run_with_mock(jobs, [_analysis()], tmp)
        seen = json.loads((Path(tmp) / "seen.json").read_text())
    assert "xyz" in seen
    assert seen["xyz"]["applied"] is False
