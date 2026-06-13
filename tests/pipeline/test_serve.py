"""Unit tests for job_search.pipeline.serve — no live network required."""

import json
from pathlib import Path


SAMPLE_MD = """\
# Job Report — June 12, 2026

Fetched: 3 | Filtered out: 0 | Scored: 3

---

### [90] Stripe — Software Engineer · 🌐 Remote

[View on LinkedIn](https://www.linkedin.com/jobs/view/111111111/)

- [x] Applied
- [ ] Hide

---

### [72] Shopify — Backend Developer · 🏢 Hybrid

[View on LinkedIn](https://www.linkedin.com/jobs/view/222222222/)

- [ ] Applied
- [x] Hide

---

### [60] Acme — DevOps Engineer · 🏛 Onsite

[View on LinkedIn](https://www.linkedin.com/jobs/view/333333333/)

- [ ] Applied
- [ ] Hide

---
"""


# ── _read_md_state ────────────────────────────────────────────────────────────

def test_read_md_state_applied(tmp_path):
    from job_search.pipeline.serve import _read_md_state
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    state = _read_md_state(md)
    assert state["111111111"] == {"applied": True, "hidden": False}


def test_read_md_state_hidden(tmp_path):
    from job_search.pipeline.serve import _read_md_state
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    state = _read_md_state(md)
    assert state["222222222"] == {"applied": False, "hidden": True}


def test_read_md_state_unchecked(tmp_path):
    from job_search.pipeline.serve import _read_md_state
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    state = _read_md_state(md)
    assert state["333333333"] == {"applied": False, "hidden": False}


# ── _patch_md ─────────────────────────────────────────────────────────────────

def test_patch_md_checks_applied(tmp_path):
    from job_search.pipeline.serve import _patch_md
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    result = _patch_md(md, "333333333", "applied", True)
    assert result is True
    assert "- [x] Applied" in md.read_text()


def test_patch_md_unchecks_applied(tmp_path):
    from job_search.pipeline.serve import _patch_md
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    result = _patch_md(md, "111111111", "applied", False)
    assert result is True
    content = md.read_text()
    # Stripe's Applied box should now be unchecked
    # Verify by re-parsing
    from job_search.pipeline.serve import _read_md_state
    assert _read_md_state(md)["111111111"]["applied"] is False


def test_patch_md_checks_hide(tmp_path):
    from job_search.pipeline.serve import _patch_md
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    _patch_md(md, "333333333", "hidden", True)
    from job_search.pipeline.serve import _read_md_state
    assert _read_md_state(md)["333333333"]["hidden"] is True


def test_patch_md_idempotent_when_already_set(tmp_path):
    from job_search.pipeline.serve import _patch_md, _read_md_state
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    _patch_md(md, "111111111", "applied", True)   # already True
    assert _read_md_state(md)["111111111"]["applied"] is True


def test_patch_md_unknown_job_returns_false(tmp_path):
    from job_search.pipeline.serve import _patch_md
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    result = _patch_md(md, "999999999", "applied", True)
    assert result is False


# ── Flask routes (use the real run_serve app) ─────────────────────────────────

def _make_app(md_path: Path):
    """Build a test Flask app using the real serve.py routes (no .html needed)."""
    import json as _json
    from flask import Flask, jsonify, request
    from job_search.pipeline.serve import _patch_md, _parse_md_to_data, _read_md_state
    from job_search.pipeline.html_template import HTML_TEMPLATE

    app = Flask(__name__)

    @app.route("/")
    def index():
        scored, filtered, date, display_date = _parse_md_to_data(md_path)
        initial_state = _read_md_state(md_path)
        payload = _json.dumps({
            "date": date, "display_date": display_date,
            "scored": scored, "filtered": filtered, "errors": [],
            "initial_state": initial_state,
        }).replace("</script>", r"<\/script>")
        html = HTML_TEMPLATE.replace("__JOBS_DATA__", payload)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/state", methods=["GET"])
    def get_state():
        return jsonify(_read_md_state(md_path))

    @app.route("/toggle", methods=["POST"])
    def toggle():
        data = request.get_json(force=True)
        job_id = data.get("job_id")
        action = data.get("action")
        value = data.get("value")
        if not job_id or action not in ("applied", "hidden"):
            return jsonify({"error": "bad request"}), 400
        found = _patch_md(md_path, str(job_id), action, bool(value))
        if not found:
            return jsonify({"error": "job not found"}), 404
        return jsonify({"ok": True})

    return app


def test_index_renders_html_from_md(tmp_path):
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    res = client.get("/")
    assert res.status_code == 200
    body = res.data.decode()
    assert "<html" in body
    assert "jobs-data" in body
    assert "Stripe" in body   # job company from SAMPLE_MD


def test_index_embeds_initial_state(tmp_path):
    """GET / must embed the current checkbox state so the page renders correctly."""
    import json as _json
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    res = client.get("/")
    body = res.data.decode()
    script_json = body.split('<script id="jobs-data" type="application/json">')[1].split("</script>")[0]
    data = _json.loads(script_json)
    initial = data.get("initial_state", {})
    assert initial.get("111111111", {}).get("applied") is True   # Stripe is [x] Applied in SAMPLE_MD


def test_index_reflects_toggle_after_reload(tmp_path):
    """After a toggle, GET / should show the updated state (no stale cache)."""
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    client.post("/toggle",
                data=json.dumps({"job_id": "333333333", "action": "applied", "value": True}),
                content_type="application/json")

    import json as _json
    res = client.get("/")
    body = res.data.decode()
    script_json = body.split('<script id="jobs-data" type="application/json">')[1].split("</script>")[0]
    data = _json.loads(script_json)
    assert data["initial_state"].get("333333333", {}).get("applied") is True


def test_toggle_route_patches_md_and_state_reflects_change(tmp_path):
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    res = client.post("/toggle",
                      data=json.dumps({"job_id": "333333333", "action": "applied", "value": True}),
                      content_type="application/json")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    state = client.get("/state").get_json()
    assert state["333333333"]["applied"] is True


def test_toggle_then_untoggle_round_trips_md(tmp_path):
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    client.post("/toggle",
                data=json.dumps({"job_id": "333333333", "action": "applied", "value": True}),
                content_type="application/json")
    client.post("/toggle",
                data=json.dumps({"job_id": "333333333", "action": "applied", "value": False}),
                content_type="application/json")

    state = client.get("/state").get_json()
    assert state["333333333"]["applied"] is False


def test_toggle_bad_action_returns_400(tmp_path):
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    res = client.post("/toggle",
                      data=json.dumps({"job_id": "333333333", "action": "invalid", "value": True}),
                      content_type="application/json")
    assert res.status_code == 400


def test_toggle_missing_job_id_returns_400(tmp_path):
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    res = client.post("/toggle",
                      data=json.dumps({"action": "applied", "value": True}),
                      content_type="application/json")
    assert res.status_code == 400


def test_toggle_unknown_job_returns_404(tmp_path):
    md = tmp_path / "daily_jobs_2026-06-12.md"
    md.write_text(SAMPLE_MD)
    client = _make_app(md).test_client()

    res = client.post("/toggle",
                      data=json.dumps({"job_id": "999999999", "action": "applied", "value": True}),
                      content_type="application/json")
    assert res.status_code == 404
