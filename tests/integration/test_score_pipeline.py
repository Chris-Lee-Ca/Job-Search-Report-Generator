"""
Integration tests for job_search.pipeline.score.run_score_filter — mocked LLM, real config.

Pure-logic unit tests (_effective_score, _format_job_section, build_provider, etc.)
live in tests/pipeline/test_score.py.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from job_search.providers.llm.base import JobAnalysis


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


_MOCK_CONFIG = {
    "llm": {"provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY"},
    "hard_filter_criteria": [],
    "scoring": {"remote_score_bonus": 5},
}


def _run_with_mock(jobs: list, analyses: list, tmp_dir: str) -> str:
    """Run score_filter against mock jobs and return the output markdown content."""
    raw_path = Path(tmp_dir) / "raw_jobs_2026-05-14.json"
    raw_path.write_text(json.dumps(jobs))

    provider = _MockProvider(analyses)
    seen_path = Path(tmp_dir) / "seen.json"
    out_dir = Path(tmp_dir)

    with patch("job_search.pipeline.score.build_provider", return_value=provider), \
         patch("job_search.pipeline.score.load_config", return_value=_MOCK_CONFIG), \
         patch("job_search.pipeline.score.load_resume", return_value="Mock resume content"), \
         patch("job_search.pipeline.score.load_seen_jobs", return_value={}), \
         patch("job_search.pipeline.score.save_seen_jobs") as mock_save, \
         patch("job_search.pipeline.score.OUTPUT_DIR", out_dir):
        from job_search.pipeline.score import run_score_filter
        run_score_filter(str(raw_path))

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

    seen_capture = {}

    def capture_save(data, path=None):
        seen_capture.update(data)

    raw_path_holder = {}

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "raw_jobs_2026-05-14.json"
        raw_path.write_text(json.dumps(jobs))
        out_dir = Path(tmp)

        with patch("job_search.pipeline.score.build_provider", return_value=_MockProvider([_analysis()])), \
             patch("job_search.pipeline.score.load_config", return_value=_MOCK_CONFIG), \
             patch("job_search.pipeline.score.load_resume", return_value="Resume"), \
             patch("job_search.pipeline.score.load_seen_jobs", return_value={}), \
             patch("job_search.pipeline.score.save_seen_jobs", side_effect=capture_save), \
             patch("job_search.pipeline.score.OUTPUT_DIR", out_dir):
            from job_search.pipeline.score import run_score_filter
            run_score_filter(str(raw_path))

    assert "xyz" in seen_capture
    assert seen_capture["xyz"]["applied"] is False
