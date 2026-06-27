"""Unit tests for job_search.config — no live network required."""

SAMPLE_CONFIG_YAML = """\
linkedin:
  delay_multiplier: 0.5

  pre_filter:
    # Companies to block outright (case-insensitive substring match on company name).
    # Add names exactly as they appear on LinkedIn.
    blocked_companies:
      - "Fire Feed"
      - "Quik Hire Staffing"

    staff_title_pattern: '\\bstaff\\b'
"""


def test_add_blocked_company_appends_new_entry(tmp_path):
    from job_search.config import add_blocked_company
    config = tmp_path / "config.yaml"
    config.write_text(SAMPLE_CONFIG_YAML)

    result = add_blocked_company("Acme Corp", config)

    assert result is True
    text = config.read_text()
    assert '- "Acme Corp"' in text
    # existing entries and trailing comment/key are untouched
    assert '- "Fire Feed"' in text
    assert "staff_title_pattern" in text


def test_add_blocked_company_duplicate_case_insensitive_is_noop(tmp_path):
    from job_search.config import add_blocked_company
    config = tmp_path / "config.yaml"
    config.write_text(SAMPLE_CONFIG_YAML)

    result = add_blocked_company("fire feed", config)

    assert result is False
    assert config.read_text().count('"Fire Feed"') == 1


def test_add_blocked_company_preserves_comments(tmp_path):
    from job_search.config import add_blocked_company
    config = tmp_path / "config.yaml"
    config.write_text(SAMPLE_CONFIG_YAML)

    add_blocked_company("Acme Corp", config)

    text = config.read_text()
    assert "# Companies to block outright" in text
    assert "# Add names exactly as they appear on LinkedIn." in text


def test_add_blocked_company_escapes_embedded_quotes(tmp_path):
    from job_search.config import add_blocked_company
    config = tmp_path / "config.yaml"
    config.write_text(SAMPLE_CONFIG_YAML)

    add_blocked_company('Weird "Quoted" Co', config)

    assert '- "Weird \\"Quoted\\" Co"' in config.read_text()


def test_add_blocked_company_missing_section_raises(tmp_path):
    from job_search.config import add_blocked_company
    config = tmp_path / "config.yaml"
    config.write_text("linkedin:\n  delay_multiplier: 0.5\n")

    try:
        add_blocked_company("Acme Corp", config)
        assert False, "expected ValueError"
    except ValueError:
        pass
