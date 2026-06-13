"""Unit tests for job_search.pipeline.score — no LLM or external I/O required."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from job_search.providers.llm.base import JobAnalysis


def _analysis(**overrides) -> JobAnalysis:
    defaults = dict(
        should_filter=False, filter_reason=None,
        score=70,
        matched_required_skills=["Python"], unmatched_required_skills=[], matched_nice_skills=["Docker"],
        min_years_required=0,
        seniority_required="Mid-level (2-4 yrs)",
        work_mode="Remote", industry="Tech",
    )
    defaults.update(overrides)
    return JobAnalysis(**defaults)


def _sample_job(**overrides):
    base = dict(
        id="123456", title="Software Engineer", company="Acme Corp",
        location="Vancouver, BC", employment_type="Full-time",
        url="https://www.linkedin.com/jobs/view/123456/",
        description="We need a Python engineer to build things.",
    )
    base.update(overrides)
    return base


# ── _effective_score ─────────────────────────────────────────────────────────

def test_remote_bonus_applied():
    from job_search.pipeline.score import _effective_score
    assert _effective_score(70, "Remote", 5) == 75

def test_hybrid_gets_half_bonus():
    from job_search.pipeline.score import _effective_score
    assert _effective_score(70, "Hybrid", 5) == 72

def test_onsite_no_bonus():
    from job_search.pipeline.score import _effective_score
    assert _effective_score(70, "Onsite", 5) == 70

def test_score_capped_at_100():
    from job_search.pipeline.score import _effective_score
    assert _effective_score(98, "Remote", 5) == 100
    assert _effective_score(100, "Remote", 10) == 100


# ── _format_job_section ───────────────────────────────────────────────────────

def test_section_contains_score_company_title():
    from job_search.pipeline.score import _format_job_section
    out = _format_job_section(_sample_job(), _analysis(score=85))
    assert "[85]" in out
    assert "Acme Corp" in out
    assert "Software Engineer" in out

def test_section_contains_linkedin_url():
    from job_search.pipeline.score import _format_job_section
    out = _format_job_section(_sample_job(), _analysis())
    assert "https://www.linkedin.com/jobs/view/123456/" in out

def test_section_has_unchecked_applied_box():
    from job_search.pipeline.score import _format_job_section
    out = _format_job_section(_sample_job(), _analysis())
    assert "- [ ] Applied" in out

def test_section_has_unchecked_hide_box():
    from job_search.pipeline.score import _format_job_section
    out = _format_job_section(_sample_job(), _analysis())
    assert "- [ ] Hide" in out

def test_section_shows_matched_skills():
    from job_search.pipeline.score import _format_job_section
    out = _format_job_section(
        _sample_job(),
        _analysis(matched_required_skills=["Python", "Go"], matched_nice_skills=["Kubernetes"]),
    )
    assert "Python" in out
    assert "Go" in out
    assert "Kubernetes" in out

def test_section_long_description_not_included():
    from job_search.pipeline.score import _format_job_section
    long_desc = "x" * 400
    out = _format_job_section(_sample_job(description=long_desc), _analysis())
    assert long_desc not in out


# ── build_provider ────────────────────────────────────────────────────────────

def test_build_provider_returns_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    from job_search.pipeline.score import build_provider
    from job_search.providers.llm.claude import ClaudeProvider
    cfg = {"llm": {"provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY"}}
    assert isinstance(build_provider(cfg), ClaudeProvider)

def test_build_provider_returns_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    from job_search.pipeline.score import build_provider
    from job_search.providers.llm.gemini import GeminiProvider
    cfg = {"llm": {"provider": "gemini", "model": "gemini-2.0-flash", "api_key_env": "GEMINI_API_KEY"}}
    assert isinstance(build_provider(cfg), GeminiProvider)

def test_build_provider_unknown_raises():
    from job_search.pipeline.score import build_provider
    with pytest.raises(ValueError, match="Unknown provider"):
        build_provider({"llm": {"provider": "badprovider", "model": "x", "api_key_env": "X"}})


# ── max_years config interpolation ───────────────────────────────────────────

def _make_config(max_years: int) -> dict:
    return {
        "llm": {"provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY"},
        "hard_filter_criteria": [
            "Exclude internships, co-ops, or student positions",
            "Exclude roles that explicitly require {max_years} or more years of experience as a hard requirement (not just preferred)",
        ],
        "scoring": {"remote_score_bonus": 5, "max_years": max_years},
    }


def test_max_years_interpolated_into_filter_criteria(tmp_path, monkeypatch):
    """scoring.max_years must be substituted into {max_years} in hard_filter_criteria."""
    import json

    cfg = _make_config(max_years=7)
    raw = [_sample_job()]
    raw_file = tmp_path / "raw_jobs_2026-01-01.json"
    raw_file.write_text(json.dumps(raw))

    captured_criteria: list[list[str]] = []

    def fake_analyze(self, *, resume, job_title, job_description, filter_criteria):
        captured_criteria.append(filter_criteria)
        return _analysis()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    with (
        patch("job_search.pipeline.score.load_config", return_value=cfg),
        patch("job_search.pipeline.score.load_resume", return_value="resume text"),
        patch("job_search.pipeline.score.load_seen_jobs", return_value={}),
        patch("job_search.pipeline.score.save_seen_jobs"),
        patch("job_search.providers.llm.claude.ClaudeProvider.analyze_job", fake_analyze),
    ):
        from job_search.pipeline.score import run_score_filter
        run_score_filter(raw_jobs_path=str(raw_file), output_path=str(tmp_path / "out.md"))

    assert captured_criteria, "analyze_job was never called"
    criteria_text = " ".join(captured_criteria[0])
    assert "7 or more years" in criteria_text, (
        f"Expected '7 or more years' in filter_criteria but got: {criteria_text!r}"
    )
    assert "{max_years}" not in criteria_text, "Placeholder was not substituted"


def test_default_max_years_is_6(tmp_path, monkeypatch):
    """When scoring.max_years is 6 (the default), the criteria string must say '6 or more years'."""
    import json

    cfg = _make_config(max_years=6)
    raw = [_sample_job()]
    raw_file = tmp_path / "raw_jobs_2026-01-01.json"
    raw_file.write_text(json.dumps(raw))

    captured_criteria: list[list[str]] = []

    def fake_analyze(self, *, resume, job_title, job_description, filter_criteria):
        captured_criteria.append(filter_criteria)
        return _analysis()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    with (
        patch("job_search.pipeline.score.load_config", return_value=cfg),
        patch("job_search.pipeline.score.load_resume", return_value="resume text"),
        patch("job_search.pipeline.score.load_seen_jobs", return_value={}),
        patch("job_search.pipeline.score.save_seen_jobs"),
        patch("job_search.providers.llm.claude.ClaudeProvider.analyze_job", fake_analyze),
    ):
        from job_search.pipeline.score import run_score_filter
        run_score_filter(raw_jobs_path=str(raw_file), output_path=str(tmp_path / "out.md"))

    criteria_text = " ".join(captured_criteria[0])
    assert "6 or more years" in criteria_text


# ── previously-applied / hidden pre-filter ───────────────────────────────────

def _run_score_with_seen(tmp_path, monkeypatch, seen_jobs: dict):
    """Helper: run score pipeline with a given seen_jobs state, return output markdown."""
    cfg = _make_config(max_years=6)
    raw = [_sample_job()]
    raw_file = tmp_path / "raw_jobs_2026-01-01.json"
    raw_file.write_text(json.dumps(raw))
    out_file = tmp_path / "out.md"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    with (
        patch("job_search.pipeline.score.load_config", return_value=cfg),
        patch("job_search.pipeline.score.load_resume", return_value="resume text"),
        patch("job_search.pipeline.score.load_seen_jobs", return_value=seen_jobs),
        patch("job_search.pipeline.score.save_seen_jobs"),
        patch("job_search.pipeline.score.update_scored"),
        patch("job_search.providers.llm.claude.ClaudeProvider.analyze_job") as mock_llm,
    ):
        from job_search.pipeline.score import run_score_filter
        run_score_filter(raw_jobs_path=str(raw_file), output_path=str(out_file))
        return out_file.read_text(), mock_llm


def test_previously_applied_job_goes_to_filtered_section(tmp_path, monkeypatch):
    seen = {"123456": {"applied": True, "applied_date": "2026-01-01", "skip": False, "first_seen": "2026-01-01", "title": "Software Engineer", "company": "Acme Corp"}}
    out, mock_llm = _run_score_with_seen(tmp_path, monkeypatch, seen)
    mock_llm.assert_not_called()
    assert "Previously applied" in out
    assert "Filtered Out" in out


def test_hidden_job_goes_to_filtered_section(tmp_path, monkeypatch):
    seen = {"123456": {"applied": False, "applied_date": None, "skip": True, "first_seen": "2026-01-01", "title": "Software Engineer", "company": "Acme Corp"}}
    out, mock_llm = _run_score_with_seen(tmp_path, monkeypatch, seen)
    mock_llm.assert_not_called()
    assert "Hidden by user" in out
    assert "Filtered Out" in out


def test_new_job_not_in_seen_is_scored(tmp_path, monkeypatch):
    cfg = _make_config(max_years=6)
    raw = [_sample_job()]
    raw_file = tmp_path / "raw_jobs_2026-01-01.json"
    raw_file.write_text(json.dumps(raw))
    out_file = tmp_path / "out.md"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    with (
        patch("job_search.pipeline.score.load_config", return_value=cfg),
        patch("job_search.pipeline.score.load_resume", return_value="resume text"),
        patch("job_search.pipeline.score.load_seen_jobs", return_value={}),
        patch("job_search.pipeline.score.save_seen_jobs"),
        patch("job_search.pipeline.score.update_scored"),
        patch("job_search.providers.llm.claude.ClaudeProvider.analyze_job", return_value=_analysis()) as mock_llm,
    ):
        from job_search.pipeline.score import run_score_filter
        run_score_filter(raw_jobs_path=str(raw_file), output_path=str(out_file))
        mock_llm.assert_called_once()
