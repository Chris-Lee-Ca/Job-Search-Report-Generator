"""Unit tests for score_filter.py — no LLM or external I/O required."""

import json
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


def _sample_job(**overrides):
    base = dict(
        id="123456", title="Software Engineer", company="Acme Corp",
        location="Vancouver, BC", employment_type="Full-time",
        url="https://www.linkedin.com/jobs/view/123456/",
        description="We need a Python engineer to build things.",
    )
    base.update(overrides)
    return base


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

def test_section_long_description_not_included():
    from score_filter import _format_job_section
    long_desc = "x" * 400
    out = _format_job_section(_sample_job(description=long_desc), _analysis(), previously_applied=False)
    assert long_desc not in out


# ── build_provider ──────────────────────────────────────────────────────────

def test_build_provider_returns_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    from score_filter import build_provider
    from providers.claude_provider import ClaudeProvider
    cfg = {"llm": {"provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY"}}
    assert isinstance(build_provider(cfg), ClaudeProvider)

def test_build_provider_returns_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    from score_filter import build_provider
    from providers.gemini_provider import GeminiProvider
    cfg = {"llm": {"provider": "gemini", "model": "gemini-2.0-flash", "api_key_env": "GEMINI_API_KEY"}}
    assert isinstance(build_provider(cfg), GeminiProvider)

def test_build_provider_unknown_raises():
    from score_filter import build_provider
    with pytest.raises(ValueError, match="Unknown provider"):
        build_provider({"llm": {"provider": "badprovider", "model": "x", "api_key_env": "X"}})


# ── load_seen_jobs / save_seen_jobs ─────────────────────────────────────────

def test_load_seen_jobs_missing_file_returns_empty(tmp_path):
    from score_filter import load_seen_jobs
    with patch("score_filter.SEEN_JOBS_FILE", tmp_path / "nonexistent.json"):
        assert load_seen_jobs() == {}

def test_save_and_load_seen_jobs_roundtrip(tmp_path):
    from score_filter import save_seen_jobs, load_seen_jobs
    data = {"abc123": {"first_seen": "2026-05-14", "applied": False}}
    seen_path = tmp_path / "seen.json"
    with patch("score_filter.SEEN_JOBS_FILE", seen_path), \
         patch("score_filter.DATA_DIR", tmp_path):
        save_seen_jobs(data)
        result = load_seen_jobs()
    assert result == data
