"""
Integration tests for score_filter.run_score_filter — mocked LLM, real config file.

Pure-logic unit tests (_effective_score, _format_job_section, build_provider, etc.)
live in test_score_filter.py alongside the source.
"""

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
        score=70,
        matched_required_skills=["Python"], matched_nice_skills=["Docker"],
        seniority_required="Mid-level (2-4 yrs)",
        work_mode="Remote", industry="Tech",
    )
    defaults.update(overrides)
    return JobAnalysis(**defaults)


class _MockProvider:
    def __init__(self, analyses: list):
        self._queue = iter(analyses)

    def analyze_job(self, **_):
        return next(self._queue)


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

    out_files = sorted(out_dir.glob("daily_jobs_*.md"))
    assert out_files, "Output markdown was not created"
    return out_files[-1].read_text()


@pytest.mark.integration
def test_scored_job_appears_in_output():
    jobs = [{"id": "aaa", "title": "Backend Dev", "company": "Beta Inc",
              "location": "Vancouver", "url": "https://linkedin.com/jobs/view/aaa/", "description": "Python role"}]
    with tempfile.TemporaryDirectory() as tmp:
        content = _run_with_mock(jobs, [_analysis(score=80, work_mode="Remote")], tmp)
    assert "Beta Inc" in content
    assert "Backend Dev" in content

@pytest.mark.integration
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

    assert "Co1" not in content
    assert "Co2" in content

@pytest.mark.integration
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

@pytest.mark.integration
def test_new_jobs_written_to_seen_jobs():
    jobs = [{"id": "xyz", "title": "Dev", "company": "Org", "location": "",
              "url": "https://linkedin.com/jobs/view/xyz/", "description": ""}]
    with tempfile.TemporaryDirectory() as tmp:
        _run_with_mock(jobs, [_analysis()], tmp)
        seen = json.loads((Path(tmp) / "seen.json").read_text())
    assert "xyz" in seen
    assert seen["xyz"]["applied"] is False
