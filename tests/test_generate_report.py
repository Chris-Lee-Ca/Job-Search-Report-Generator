"""
Integration test for generate_report — tests full main() flow with seen_jobs.json update.

Pure-logic unit tests (parse_applied_jobs, generate_report, extract_date_from_filename)
live in test_generate_report.py alongside the source.
"""

import json
import sys
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
    from generate_report import main as gen_main

    with tempfile.TemporaryDirectory() as tmp:
        daily = Path(tmp) / "daily_jobs_2026-05-14.md"
        daily.write_text(SAMPLE_DAILY)
        seen_path = Path(tmp) / "seen.json"

        with patch("generate_report.SEEN_JOBS_FILE", seen_path), \
             patch("generate_report.DATA_DIR", Path(tmp)), \
             patch("generate_report.REPORTS_DIR", Path(tmp)):
            sys.argv = ["generate_report.py", str(daily)]
            gen_main()

        seen = json.loads(seen_path.read_text())

    assert seen["111111111"]["applied"] is True
    assert seen["111111111"]["applied_date"] == "2026-05-14"
    assert seen["333333333"]["applied"] is True
    assert "222222222" not in seen
