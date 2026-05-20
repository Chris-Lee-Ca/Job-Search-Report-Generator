"""
Integration tests for LinkedIn scraping logic — require Playwright/Chromium.

Pure-logic unit tests (pre_filter, strip_french, extract_job_id) live in
job_providers/test_linkedin_provider.py alongside the source.

Run only when changing scraping methods:
    pytest tests/test_scraper.py -v
"""

from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
MOCK_SEARCH_HTML = (FIXTURES / "linkedin_mock.html").read_text(encoding="utf-8")
MOCK_SEARCH_URL = "https://www.linkedin.com/jobs/search-results/?keywords=test"
MOCK_SEARCH_ENTRY = {"label": "test", "url": MOCK_SEARCH_URL, "remote_only": False}

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


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def provider(tmp_path):
    from job_providers.linkedin_provider import LinkedInProvider
    return LinkedInProvider(
        output_dir=tmp_path / "output",
        debug_dir=tmp_path / "debug",
        browser_data_dir=tmp_path / "browser_data",
    )

@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()

@pytest.fixture
def mock_page(browser):
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


# ── Search result ID extraction ───────────────────────────────────────────────

@pytest.mark.integration
def test_extracts_three_job_ids_from_mock(mock_page, provider):
    jobs = {}
    provider._scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, jobs, url_idx=0)
    assert len(jobs) == 3, f"Expected 3 jobs, got {len(jobs)}: {list(jobs.keys())}"

@pytest.mark.integration
def test_extracted_ids_are_correct(mock_page, provider):
    jobs = {}
    provider._scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, jobs, url_idx=0)
    assert "1111111111" in jobs
    assert "2222222222" in jobs
    assert "3333333333" in jobs

@pytest.mark.integration
def test_job_url_uses_view_format(mock_page, provider):
    jobs = {}
    provider._scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, jobs, url_idx=0)
    for job in jobs.values():
        assert "/jobs/view/" in job["url"]

@pytest.mark.integration
def test_duplicate_ids_not_added(mock_page, provider):
    existing = {"1111111111": {"id": "1111111111", "title": "Old", "company": "",
                               "location": "", "url": "", "description": ""}}
    provider._scrape_search_url(mock_page, MOCK_SEARCH_ENTRY, existing, url_idx=0)
    assert existing["1111111111"]["title"] == "Old"
    assert len(existing) == 3


# ── Detail page parsing ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_detail_title_from_page_title(detail_page, provider):
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    provider._fetch_job_detail(detail_page, job)
    assert job["title"] == "Software Engineer"

@pytest.mark.integration
def test_detail_company_from_dom(detail_page, provider):
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    provider._fetch_job_detail(detail_page, job)
    assert job["company"] == "Acme Corp"

@pytest.mark.integration
def test_detail_description_extracted(detail_page, provider):
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    provider._fetch_job_detail(detail_page, job)
    assert "Python" in job["description"]

@pytest.mark.integration
def test_detail_employment_type_extracted(detail_page, provider):
    job = {"id": "1111111111", "url": "https://www.linkedin.com/jobs/view/1111111111/",
           "title": "", "company": "", "location": "", "description": ""}
    provider._fetch_job_detail(detail_page, job)
    assert job.get("employment_type") == "Full-time"

@pytest.mark.integration
def test_detail_company_nonempty_for_all_jobs(detail_page, provider):
    expected = {
        "1111111111": "Acme Corp",
        "2222222222": "Beta Inc",
        "3333333333": "Gamma Ltd",
    }
    for job_id, expected_company in expected.items():
        job = {"id": job_id, "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
               "title": "", "company": "", "location": "", "description": ""}
        provider._fetch_job_detail(detail_page, job)
        assert job["company"] != "", f"company empty for job {job_id}"
        assert job["company"] == expected_company, f"got {job['company']!r}, want {expected_company!r}"
