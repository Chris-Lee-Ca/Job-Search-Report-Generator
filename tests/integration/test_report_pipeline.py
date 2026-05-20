"""
Integration test for job_search.pipeline.report.run_report — full flow with seen_jobs update.

Pure-logic unit tests (parse_applied_jobs, generate_report, extract_date_from_filename)
live in tests/pipeline/test_report.py.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

SAMPLE_DAILY = """\
# Job Report — May 14, 2026

Fetched: 3 | Filtered out: 1 | Scored: 2

---

### [90] Stripe — Software Engineer · 🌐 Remote
Vancouver, BC · Full-time
✅ **Required matched:** Python, REST APIs

[View on LinkedIn](https://www.linkedin.com/jobs/view/111111111/)

- [x] Applied

---

### [72] Shopify — Backend Developer · 🏢 Hybrid
Vancouver, BC · Full-time

[View on LinkedIn](https://www.linkedin.com/jobs/view/222222222/)

- [ ] Applied

---

### [60] Acme — DevOps Engineer · 🏛 Onsite

[View on LinkedIn](https://www.linkedin.com/jobs/view/333333333/)

- [x] Applied

---

## Filtered Out

- **Google — Staff Engineer** — staff-level title
"""


@pytest.mark.integration
def test_seen_jobs_updated_after_report():
    from job_search.pipeline.report import run_report

    seen_capture = {}

    def capture_save(data, path=None):
        seen_capture.update(data)

    with tempfile.TemporaryDirectory() as tmp:
        daily = Path(tmp) / "daily_jobs_2026-05-14.md"
        daily.write_text(SAMPLE_DAILY)

        with patch("job_search.pipeline.report.load_seen_jobs", return_value={}), \
             patch("job_search.pipeline.report.save_seen_jobs", side_effect=capture_save), \
             patch("job_search.pipeline.report.REPORTS_DIR", Path(tmp)):
            run_report(str(daily))

    assert seen_capture["111111111"]["applied"] is True
    assert seen_capture["111111111"]["applied_date"] == "2026-05-14"
    assert seen_capture["333333333"]["applied"] is True
    assert "222222222" not in seen_capture
