---
name: debug-scraper
description: Step-by-step process for diagnosing scraper issues — missing jobs, empty fields, wrong selectors. Trigger when user says "scraper is wrong", "jobs are missing", "fields are empty", "debug scraper", or when `/debug-scraper` is invoked.
---

# Debug Scraper

Follow these steps in order. Do not skip straight to writing new selectors.

## Steps

### 1. Run targeted tests

Run only the tests for the changed file:

| Changed file | Test command |
|---|---|
| `job_search/pipeline/fetch.py` | `pytest -m "not integration" -v` |
| `job_search/pipeline/score.py` | `pytest tests/pipeline/test_score.py tests/integration/test_score_pipeline.py -v` |
| `job_search/pipeline/report.py` | `pytest tests/pipeline/test_report.py tests/integration/test_report_pipeline.py -v` |
| `job_search/providers/scrapers/linkedin.py` | `pytest tests/providers/scrapers/test_linkedin.py tests/integration/test_scraper.py -v` |

Single test: `pytest tests/providers/scrapers/test_linkedin.py::test_name -v`

Do not claim the fix is complete if tests fail.

### 2. Check saved HTML

Every search page visit writes a snapshot to `output/debug/`:

- Search pages: `output/debug/debug_{label}_p{n}.html`
- First detail page fetched: `output/debug/debug_detail_first.html`
- Jobs with missing description: `output/debug/debug_detail_missing_desc_{id}.html`

Read the actual HTML structure before writing any new selectors — do not guess.

### 3. Run the scraper live

`python main.py fetch` is allowed and encouraged when diagnosing scraper issues. Check:
- Printed output: job counts per page, filtered reasons, description lengths
- Saved HTML in `output/debug/` alongside the printed output
