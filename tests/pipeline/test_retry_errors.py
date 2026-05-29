"""Tests for retry_errors — focus on parse correctness before any live API calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from job_search.pipeline.retry_errors import _parse_error_job_ids

# Minimal daily file that mirrors the real structure:
# scored jobs → ## Errors → ## Filtered Out
# Both the Errors and Filtered Out sections contain LinkedIn URLs,
# so the parser must stop at the next ## heading.
SAMPLE_DAILY = """\
# Job Report — May 27, 2026

Fetched: 10 | Filtered out: 2 | Scored: 5

---

### [85] Acme Corp — Software Engineer · 🌐 Remote

[View on LinkedIn](https://www.linkedin.com/jobs/view/1111111111/)

- [ ] Applied

---

## Errors — manual review needed

> These jobs could not be analysed by the AI.

- [Error Co — Bad Job](https://www.linkedin.com/jobs/view/2222222222/)
  ⚠️ `Unterminated string starting at: line 16 column 3 (char 616)`
- [Error Co — Another Bad Job](https://www.linkedin.com/jobs/view/3333333333/)
  ⚠️ `Expecting ',' delimiter: line 14 column 3 (char 600)`

---

## Filtered Out

### Too much experience required (2)

- [Filter Co — Senior Eng](https://www.linkedin.com/jobs/view/4444444444/) *(≥8 yrs)*
- [Filter Co — Staff Eng](https://www.linkedin.com/jobs/view/5555555555/) *(≥10 yrs)*
"""

SAMPLE_DAILY_NO_ERRORS = """\
# Job Report — May 27, 2026

Fetched: 5 | Filtered out: 1 | Scored: 4

---

### [85] Acme Corp — Software Engineer · 🌐 Remote

[View on LinkedIn](https://www.linkedin.com/jobs/view/1111111111/)

- [ ] Applied

---

## Filtered Out

### Too much experience required (1)

- [Filter Co — Senior Eng](https://www.linkedin.com/jobs/view/4444444444/) *(≥8 yrs)*
"""

SAMPLE_DAILY_ERRORS_LAST = """\
# Job Report — May 27, 2026

Fetched: 5 | Filtered out: 0 | Scored: 3

---

### [85] Acme Corp — Software Engineer · 🌐 Remote

[View on LinkedIn](https://www.linkedin.com/jobs/view/1111111111/)

- [ ] Applied

---

## Errors — manual review needed

- [Error Co — Bad Job](https://www.linkedin.com/jobs/view/2222222222/)
  ⚠️ `some error`
- [Error Co — Another](https://www.linkedin.com/jobs/view/3333333333/)
  ⚠️ `another error`
"""


def test_parse_error_ids_only_errors_section(tmp_path: Path):
    """Must return only the IDs from ## Errors, not from ## Filtered Out."""
    f = tmp_path / "daily_jobs_2026-05-27.md"
    f.write_text(SAMPLE_DAILY, encoding="utf-8")

    ids = _parse_error_job_ids(f)

    assert ids == ["2222222222", "3333333333"], (
        f"Expected only error section IDs, got: {ids}"
    )


def test_parse_error_ids_excludes_scored_jobs(tmp_path: Path):
    """Must not return IDs from the scored jobs section above ## Errors."""
    f = tmp_path / "daily_jobs_2026-05-27.md"
    f.write_text(SAMPLE_DAILY, encoding="utf-8")

    ids = _parse_error_job_ids(f)

    assert "1111111111" not in ids
    assert "4444444444" not in ids
    assert "5555555555" not in ids


def test_parse_error_ids_no_errors_section(tmp_path: Path):
    """Returns empty list when there is no ## Errors section."""
    f = tmp_path / "daily_jobs_2026-05-27.md"
    f.write_text(SAMPLE_DAILY_NO_ERRORS, encoding="utf-8")

    assert _parse_error_job_ids(f) == []


def test_parse_error_ids_errors_at_end_of_file(tmp_path: Path):
    """Works correctly when ## Errors is the last section (no ## Filtered Out after it)."""
    f = tmp_path / "daily_jobs_2026-05-27.md"
    f.write_text(SAMPLE_DAILY_ERRORS_LAST, encoding="utf-8")

    ids = _parse_error_job_ids(f)

    assert ids == ["2222222222", "3333333333"]


def test_parse_error_ids_count_matches(tmp_path: Path):
    """Sanity-check the exact count of returned IDs."""
    f = tmp_path / "daily_jobs_2026-05-27.md"
    f.write_text(SAMPLE_DAILY, encoding="utf-8")

    ids = _parse_error_job_ids(f)

    assert len(ids) == 2
