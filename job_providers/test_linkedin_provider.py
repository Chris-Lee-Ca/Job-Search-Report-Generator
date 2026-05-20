"""Unit tests for linkedin_provider.py — pure logic, no browser required."""


# ── _passes_pre_filter ────────────────────────────────────────────────────────

def test_pre_filter_metro_van_always_passes():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Vancouver, BC")
    assert ok

def test_pre_filter_staff_title_blocked():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Staff Engineer", "Vancouver, BC")
    assert not ok
    assert "staff" in reason

def test_pre_filter_non_bc_city_blocked_without_remote():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Toronto, ON")
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_non_bc_city_blocked_with_remote():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Toronto, ON · Remote")
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_non_bc_city_blocked_assume_remote():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Calgary, AB · Remote", assume_remote=True)
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_canada_remote_passes():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Canada · Remote")
    assert ok

def test_pre_filter_bc_remote_passes():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "British Columbia, Canada · Remote")
    assert ok

def test_pre_filter_non_metro_bc_onsite_blocked():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Victoria, BC")
    assert not ok
    assert "non-Metro BC onsite" in reason

def test_pre_filter_assume_remote_no_location_context_passes():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Remote", assume_remote=True)
    assert ok

def test_pre_filter_blocked_company_fire_feed():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Vancouver, BC", company="Fire Feed")
    assert not ok
    assert "blocked company" in reason

def test_pre_filter_blocked_company_quik_hire():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, reason = _passes_pre_filter("Developer", "Canada · Remote", company="Quik Hire Staffing")
    assert not ok
    assert "blocked company" in reason

def test_pre_filter_blocked_company_case_insensitive():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, _ = _passes_pre_filter("Developer", "Vancouver, BC", company="FIRE FEED")
    assert not ok

def test_pre_filter_non_blocked_company_passes():
    from job_providers.linkedin_provider import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Vancouver, BC", company="Acme Corp")
    assert ok


# ── _strip_french_section ────────────────────────────────────────────────────

def test_strip_french_version_francaise():
    from job_providers.linkedin_provider import _strip_french_section
    desc = "We are hiring a Python developer. Version française Nous cherchons un développeur."
    result = _strip_french_section(desc)
    assert result == "We are hiring a Python developer."
    assert "Nous cherchons" not in result

def test_strip_french_en_francais():
    from job_providers.linkedin_provider import _strip_french_section
    desc = "Great opportunity. En français Bonne opportunité."
    result = _strip_french_section(desc)
    assert "Bonne" not in result
    assert "Great opportunity" in result

def test_strip_french_no_marker_unchanged():
    from job_providers.linkedin_provider import _strip_french_section
    desc = "We are looking for a Software Engineer with Python experience."
    assert _strip_french_section(desc) == desc


# ── extract_job_id ───────────────────────────────────────────────────────────

def test_extract_job_id_from_view_url():
    from job_providers.linkedin_provider import extract_job_id
    assert extract_job_id("https://www.linkedin.com/jobs/view/1234567890/") == "1234567890"

def test_extract_job_id_from_currentjobid():
    from job_providers.linkedin_provider import extract_job_id
    assert extract_job_id("/jobs/search-results/?currentJobId=9876543210&ref=x") == "9876543210"

def test_extract_job_id_returns_none_for_garbage():
    from job_providers.linkedin_provider import extract_job_id
    assert extract_job_id("https://www.linkedin.com/feed/") is None
    assert extract_job_id("") is None
