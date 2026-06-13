"""Unit tests for job_search.providers.scrapers.linkedin — pure logic, no browser."""

import pytest


# ── cfg fixture ───────────────────────────────────────────────────────────────
# Mirrors the linkedin: section of config/config.yaml so tests are independent
# of the real config file.

@pytest.fixture
def linkedin_cfg():
    return {
        "pre_filter": {
            "blocked_companies": ["Fire Feed", "Quik Hire Staffing"],
            "staff_title_pattern": (
                r"\bstaff\s+(engineer|developer|software|platform|ml|sre|sde|"
                r"backend|frontend|full.?stack|data|cloud|devops|infra|architect)"
            ),
            "lead_principal_title_pattern": (
                r"\b(lead|principal)\s+(developer|engineer|software|platform|ml|sre|sde|"
                r"backend|frontend|full.?stack|data|cloud|devops|infra|architect)"
                r"|\bteam\s+lead\b"
                r"|\btech\s+lead\b"
                r"|\bengineering\s+lead\b"
                r"|\bmanager\b|\bdirector\b|\bdata\s+(scientist|analyst)\b|\bdevops\b"
                r"|\bqa\b|\bsdet\b"
                r"|\btest\s+(engineer|developer|lead|architect)\b"
                r"|\bquality\s+(engineer|assurance|designer|analyst)\b"
                r"|\bautomation\s+(engineer|developer|tester)\b"
            ),
        },
        "location_filter": {
            "metro_vancouver": [
                "vancouver", "burnaby", "richmond", "surrey", "coquitlam",
                "new westminster", "north vancouver", "west vancouver", "delta",
                "langley", "port moody", "port coquitlam", "maple ridge",
                "pitt meadows", "abbotsford", "white rock",
            ],
            "blocked_non_bc_cities": [
                "toronto", "mississauga", "brampton", "markham", "vaughan", "oakville",
                "burlington", "richmond hill", "oshawa", "barrie", "guelph", "kingston",
                "windsor", "sudbury", "thunder bay", "whitby", "ajax", "pickering",
                "newmarket", "aurora", "kanata", "scarborough", "north york", "etobicoke",
                "ontario", "calgary", "edmonton", "ottawa", "montreal", "winnipeg",
                "hamilton", "london", "waterloo", "kitchener", "saskatoon", "regina",
                "halifax", "alberta", "quebec", "manitoba", "saskatchewan",
                "nova scotia", "new brunswick", "newfoundland", "prince edward",
            ],
        },
    }


# ── _passes_pre_filter ────────────────────────────────────────────────────────

def test_pre_filter_metro_van_always_passes(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Vancouver, BC", linkedin_cfg)
    assert ok

def test_pre_filter_staff_title_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Staff Engineer", "Vancouver, BC", linkedin_cfg)
    assert not ok
    assert "staff" in reason

def test_pre_filter_non_bc_city_blocked_without_remote(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Toronto, ON", linkedin_cfg)
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_non_bc_city_blocked_with_remote(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Toronto, ON · Remote", linkedin_cfg)
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_non_bc_city_blocked_assume_remote(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Calgary, AB · Remote", linkedin_cfg, assume_remote=True)
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_canada_remote_passes(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Canada · Remote", linkedin_cfg)
    assert ok

def test_pre_filter_bc_remote_passes(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "British Columbia, Canada · Remote", linkedin_cfg)
    assert ok

def test_pre_filter_non_metro_bc_onsite_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Victoria, BC", linkedin_cfg)
    assert not ok
    assert "non-Metro BC onsite" in reason

def test_pre_filter_assume_remote_no_location_context_passes(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Remote", linkedin_cfg, assume_remote=True)
    assert ok

def test_pre_filter_blocked_company_fire_feed(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Vancouver, BC", linkedin_cfg, company="Fire Feed")
    assert not ok
    assert "blocked company" in reason

def test_pre_filter_blocked_company_quik_hire(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Developer", "Canada · Remote", linkedin_cfg, company="Quik Hire Staffing")
    assert not ok
    assert "blocked company" in reason

def test_pre_filter_blocked_company_case_insensitive(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Developer", "Vancouver, BC", linkedin_cfg, company="FIRE FEED")
    assert not ok

def test_pre_filter_non_blocked_company_passes(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Vancouver, BC", linkedin_cfg, company="Acme Corp")
    assert ok


# ── QA / testing title blocks ─────────────────────────────────────────────────

def test_pre_filter_qa_automation_engineer_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("QA Automation Engineer", "Vancouver, BC", linkedin_cfg)
    assert not ok
    assert "lead/principal" in reason

def test_pre_filter_qa_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Senior QA Developer", "Canada · Remote", linkedin_cfg)
    assert not ok

def test_pre_filter_sdet_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("SDET II", "Vancouver, BC", linkedin_cfg)
    assert not ok

def test_pre_filter_test_engineer_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Test Engineer", "Canada · Remote", linkedin_cfg)
    assert not ok

def test_pre_filter_quality_assurance_engineer_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Quality Assurance Engineer", "Vancouver, BC", linkedin_cfg)
    assert not ok

def test_pre_filter_automation_engineer_blocked(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, reason = _passes_pre_filter("Automation Engineer", "Canada · Remote", linkedin_cfg)
    assert not ok

def test_pre_filter_software_engineer_not_blocked_by_qa_patterns(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Vancouver, BC", linkedin_cfg)
    assert ok

def test_pre_filter_backend_engineer_not_blocked_by_qa_patterns(linkedin_cfg):
    from job_search.providers.scrapers.linkedin import _passes_pre_filter
    ok, _ = _passes_pre_filter("Backend Engineer", "Canada · Remote", linkedin_cfg)
    assert ok


# ── _strip_french_section ─────────────────────────────────────────────────────

def test_strip_french_version_francaise():
    from job_search.providers.scrapers.linkedin import _strip_french_section
    desc = "We are hiring a Python developer. Version française Nous cherchons un développeur."
    result = _strip_french_section(desc)
    assert result == "We are hiring a Python developer."
    assert "Nous cherchons" not in result

def test_strip_french_en_francais():
    from job_search.providers.scrapers.linkedin import _strip_french_section
    desc = "Great opportunity. En français Bonne opportunité."
    result = _strip_french_section(desc)
    assert "Bonne" not in result
    assert "Great opportunity" in result

def test_strip_french_no_marker_unchanged():
    from job_search.providers.scrapers.linkedin import _strip_french_section
    desc = "We are looking for a Software Engineer with Python experience."
    assert _strip_french_section(desc) == desc


# ── extract_job_id ────────────────────────────────────────────────────────────

def test_extract_job_id_from_view_url():
    from job_search.providers.scrapers.linkedin import extract_job_id
    assert extract_job_id("https://www.linkedin.com/jobs/view/1234567890/") == "1234567890"

def test_extract_job_id_from_currentjobid():
    from job_search.providers.scrapers.linkedin import extract_job_id
    assert extract_job_id("/jobs/search-results/?currentJobId=9876543210&ref=x") == "9876543210"

def test_extract_job_id_returns_none_for_garbage():
    from job_search.providers.scrapers.linkedin import extract_job_id
    assert extract_job_id("https://www.linkedin.com/feed/") is None
    assert extract_job_id("") is None


# ── _filter_blocked_companies ─────────────────────────────────────────────────
# These tests confirm that company filtering happens AFTER detail fetch,
# using the company name populated from the detail page (not the card preview).

@pytest.fixture
def provider(linkedin_cfg, tmp_path):
    from job_search.providers.scrapers.linkedin import LinkedInProvider
    return LinkedInProvider(
        output_dir=tmp_path,
        debug_dir=tmp_path,
        browser_data_dir=tmp_path,
        linkedin_cfg=linkedin_cfg,
    )

def _make_jobs(*companies):
    return {
        str(i): {"id": str(i), "title": "Software Engineer", "company": c, "location": "Vancouver, BC"}
        for i, c in enumerate(companies)
    }

def test_filter_blocked_removes_quik_hire(provider):
    jobs = _make_jobs("Quik Hire Staffing", "Acme Corp")
    result = provider._filter_blocked_companies(jobs)
    companies = [j["company"] for j in result.values()]
    assert "Quik Hire Staffing" not in companies
    assert "Acme Corp" in companies

def test_filter_blocked_removes_fire_feed(provider):
    jobs = _make_jobs("Fire Feed", "Good Company")
    result = provider._filter_blocked_companies(jobs)
    assert all(j["company"] != "Fire Feed" for j in result.values())

def test_filter_blocked_case_insensitive(provider):
    jobs = _make_jobs("QUIK HIRE STAFFING", "quik hire staffing", "Quik Hire Staffing")
    result = provider._filter_blocked_companies(jobs)
    assert len(result) == 0

def test_filter_blocked_passes_non_blocked(provider):
    jobs = _make_jobs("Acme Corp", "Beta Inc", "Gamma Ltd")
    result = provider._filter_blocked_companies(jobs)
    assert len(result) == 3

def test_filter_blocked_empty_company_field_passes(provider):
    # Jobs from _read_preview have company="" — they must not be blocked by mistake.
    jobs = _make_jobs("")
    result = provider._filter_blocked_companies(jobs)
    assert len(result) == 1
