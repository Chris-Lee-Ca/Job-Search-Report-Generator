"""
Tests for fetch_jobs.py scraping logic.

Uses Playwright route interception to serve local mock HTML instead of hitting LinkedIn.
If these tests pass but the live scraper still returns 0 jobs or empty fields, check
output/debug_search_url*_p1.html (saved on every run) and update the mock fixture.
"""

from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
MOCK_SEARCH_HTML = (FIXTURES / "linkedin_mock.html").read_text(encoding="utf-8")
MOCK_SEARCH_URL = "https://www.linkedin.com/jobs/search-results/?keywords=test"
MOCK_SEARCH_ENTRY = {"label": "test", "url": MOCK_SEARCH_URL, "remote_only": False}

# Per-job detail pages — company comes from a[href*="/company/"] DOM element
def _detail_html(title: str, company: str, description: str = "Python engineer role.") -> str:
    slug = company.lower().replace(" ", "-")
    return f"""<html>
<head><title>{title} at {company} | LinkedIn</title></head>
<body>
  <a href="/company/{slug}/">{company}</a>
  <div class="show-more-less-html__markup">{description}</div>
  <span class="description__job-criteria-text">Full-time</span>
</body>
</html>"""

MOCK_DETAILS = {
    "1111111111": _detail_html("Software Engineer", "Acme Corp", "Python and Go required."),
    "2222222222": _detail_html("Full Stack Developer", "Beta Inc", "React and Node.js role."),
    "3333333333": _detail_html("Platform Engineer", "Gamma Ltd", "Kubernetes and AWS required."),
}


# ── _passes_pre_filter ────────────────────────────────────────────────────────

def test_pre_filter_metro_van_always_passes():
    from fetch_jobs import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Vancouver, BC")
    assert ok

def test_pre_filter_staff_title_blocked():
    from fetch_jobs import _passes_pre_filter
    ok, reason = _passes_pre_filter("Staff Engineer", "Vancouver, BC")
    assert not ok
    assert "staff" in reason

def test_pre_filter_non_bc_city_blocked_without_remote():
    from fetch_jobs import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Toronto, ON")
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_non_bc_city_blocked_with_remote():
    from fetch_jobs import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Toronto, ON · Remote")
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_non_bc_city_blocked_assume_remote():
    from fetch_jobs import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Calgary, AB · Remote", assume_remote=True)
    assert not ok
    assert "non-BC city" in reason

def test_pre_filter_canada_remote_passes():
    from fetch_jobs import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Canada · Remote")
    assert ok

def test_pre_filter_bc_remote_passes():
    from fetch_jobs import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "British Columbia, Canada · Remote")
    assert ok

def test_pre_filter_non_metro_bc_onsite_blocked():
    from fetch_jobs import _passes_pre_filter
    ok, reason = _passes_pre_filter("Software Engineer", "Victoria, BC")
    assert not ok
    assert "non-Metro BC onsite" in reason

def test_pre_filter_assume_remote_no_location_context_passes():
    from fetch_jobs import _passes_pre_filter
    ok, _ = _passes_pre_filter("Software Engineer", "Remote", assume_remote=True)
    assert ok


# ── extract_job_id ───────────────────────────────────────────────────────────

def test_extract_job_id_from_view_url():
    from fetch_jobs import extract_job_id
    assert extract_job_id("https://www.linkedin.com/jobs/view/1234567890/") == "1234567890"

def test_extract_job_id_from_currentjobid():
    from fetch_jobs import extract_job_id
    assert extract_job_id("/jobs/search-results/?currentJobId=9876543210&ref=x") == "9876543210"

def test_extract_job_id_returns_none_for_garbage():
    from fetch_jobs import extract_job_id
    assert extract_job_id("https://www.linkedin.com/feed/") is None
    assert extract_job_id("") is None


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def mock_page(browser):
    """Playwright page with LinkedIn URLs intercepted by mock HTML."""
    context = browser.new_context()
    page = context.new_page()

    def handle(route):
        url = route.request.url
        for job_id, html in MOCK_DETAILS.items():
            if job_id in url:
                route.fulfill(content_type="text/html", body=html)
                return
        route.fulfill(content_type="text/html", body=MOCK_SEARCH_HTML)

    page.route("https://www.linkedin.com/**", handle)
    yield page
    context.close()


# ── ID extraction from search results ────────────────────────────────────────

def test_extracts_three_job_ids_from_mock(mock_page):
    from fetch_jobs import _scrape_search_url
    jobs = {}
    _scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, jobs, url_idx=0)
    assert len(jobs) == 3, f"Expected 3 jobs, got {len(jobs)}: {list(jobs.keys())}"

def test_extracted_ids_are_correct(mock_page):
    from fetch_jobs import _scrape_search_url
    jobs = {}
    _scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, jobs, url_idx=0)
    assert "1111111111" in jobs
    assert "2222222222" in jobs
    assert "3333333333" in jobs

def test_job_url_uses_view_format(mock_page):
    from fetch_jobs import _scrape_search_url
    jobs = {}
    _scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, jobs, url_idx=0)
    for job in jobs.values():
        assert "/jobs/view/" in job["url"]

def test_duplicate_ids_not_added(mock_page):
    from fetch_jobs import _scrape_search_url
    existing = {"1111111111": {"id": "1111111111", "title": "Old", "company": "",
                               "location": "", "url": "", "description": ""}}
    _scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, existing, url_idx=0)
    assert existing["1111111111"]["title"] == "Old"  # not overwritten
    assert len(existing) == 3  # 2 new added


# ── detail page parsing ───────────────────────────────────────────────────────

@pytest.fixture
def detail_page(browser):
    context = browser.new_context()
    page = context.new_page()

    def handle(route):
        for job_id, html in MOCK_DETAILS.items():
            if job_id in route.request.url:
                route.fulfill(content_type="text/html", body=html)
                return
        route.fulfill(content_type="text/html", body="<html><body>Not found</body></html>")

    page.route("https://www.linkedin.com/**", handle)
    yield page
    context.close()

def test_detail_title_from_page_title(detail_page):
    from fetch_jobs import _fetch_job_detail
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    _fetch_job_detail(detail_page, job)
    assert job["title"] == "Software Engineer"

def test_detail_company_from_dom(detail_page):
    from fetch_jobs import _fetch_job_detail
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    _fetch_job_detail(detail_page, job)
    assert job["company"] == "Acme Corp"

def test_detail_description_extracted(detail_page):
    from fetch_jobs import _fetch_job_detail
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    _fetch_job_detail(detail_page, job)
    assert "Python" in job["description"]

def test_detail_employment_type_extracted(detail_page):
    from fetch_jobs import _fetch_job_detail
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    _fetch_job_detail(detail_page, job)
    assert job.get("employment_type") == "Full-time"

def test_detail_company_nonempty_for_all_jobs(detail_page):
    from fetch_jobs import _fetch_job_detail
    expected = {
        "1111111111": "Acme Corp",
        "2222222222": "Beta Inc",
        "3333333333": "Gamma Ltd",
    }
    for job_id, expected_company in expected.items():
        job = {"id": job_id, "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
               "title": "", "company": "", "location": "", "description": ""}
        _fetch_job_detail(detail_page, job)
        assert job["company"] != "", f"company empty for job {job_id}"
        assert job["company"] == expected_company, f"got {job['company']!r}, want {expected_company!r}"
