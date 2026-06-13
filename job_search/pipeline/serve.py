"""Flask dev server for the interactive daily job review.

The markdown file is the only file that matters — no static HTML is written to disk.
Every GET / re-parses the .md and renders fresh HTML.
"""

from __future__ import annotations

import json
import re
import webbrowser
from pathlib import Path


# ── Markdown → structured data ────────────────────────────────────────────────

_EMOJI_MODE = {"🌐": "Remote", "🏢": "Hybrid", "🏛": "Onsite", "❓": "Unknown"}


def _skill_bullets(section: str, marker: str) -> list[str]:
    m = re.search(rf"{re.escape(marker)}[^\n]*\n((?:  - .+\n?)*)", section)
    if not m:
        return []
    return [
        ln.strip().lstrip("- ").strip()
        for ln in m.group(1).splitlines()
        if ln.startswith("  -")
    ]


def _parse_md_to_data(md_path: Path) -> tuple[list[dict], list[dict], str, str]:
    """Parse a daily .md file into (scored_jobs, filtered_jobs, date, display_date)."""
    content = md_path.read_text(encoding="utf-8")

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", md_path.name)
    date = date_match.group(1) if date_match else ""
    display_match = re.search(r"^# Job Report — (.+)$", content, re.MULTILINE)
    display_date = display_match.group(1).strip() if display_match else date

    scored: list[dict] = []
    filtered: list[dict] = []

    raw_sections = re.split(r"\n---\n", content)
    current_filtered_cat = "Filtered"
    in_filtered = False

    for sec in raw_sections:
        sec = sec.strip()

        if sec.startswith("## Filtered Out") or in_filtered:
            in_filtered = True
            for cat_m in re.finditer(r"^### (.+?) \(\d+\)", sec, re.MULTILINE):
                current_filtered_cat = cat_m.group(1).strip()
            for link_m in re.finditer(
                r"^- \[(.+?)\]\((https?://[^\)]+)\)", sec, re.MULTILINE
            ):
                raw_name = link_m.group(1)
                name = re.sub(r"\s*\*\([^)]*\)\*", "", raw_name).strip()
                parts = name.split(" — ", 1)
                filtered.append(
                    {
                        "company": parts[0].strip(),
                        "title": parts[1].strip() if len(parts) > 1 else name,
                        "url": link_m.group(2),
                        "reason": current_filtered_cat,
                    }
                )
            continue

        heading_match = re.match(r"### \[(\d+)\]\s+(.+)", sec)
        if not heading_match:
            continue

        score = int(heading_match.group(1))
        rest = re.sub(r"\s*⚠️.*$", "", heading_match.group(2)).strip()

        dash_parts = rest.split(" — ", 1)
        company = dash_parts[0].strip() if len(dash_parts) > 1 else ""
        title_mode = dash_parts[1] if len(dash_parts) > 1 else dash_parts[0]

        dot_parts = title_mode.rsplit(" · ", 1)
        title = dot_parts[0].strip()
        work_mode = "Unknown"
        if len(dot_parts) > 1:
            for emoji, mode in _EMOJI_MODE.items():
                if emoji in dot_parts[1]:
                    work_mode = mode
                    break

        url_m = re.search(r"\[View on LinkedIn\]\((https?://[^\)]+)\)", sec)
        url = url_m.group(1) if url_m else ""
        job_id_m = re.search(r"/jobs/view/(\d+)", url)
        job_id = job_id_m.group(1) if job_id_m else ""

        location = employment_type = ""
        for line in sec.splitlines()[1:]:
            s = line.strip()
            if s and not s.startswith(
                ("✅", "❌", "⭐", "🔧", "📊", "💰", "🏭", "[", "-", "#", ">")
            ):
                meta = [p.strip() for p in s.split(" · ")]
                location = meta[0]
                employment_type = meta[1] if len(meta) > 1 else ""
                break

        tech_m = re.search(r"🔧 \*\*Tech:\*\* (.+)", sec)
        sen_m = re.search(r"📊 (.+)", sec)
        sal_m = re.search(r"💰 (.+)", sec)
        ind_m = re.search(r"🏭 (.+)", sec)

        scored.append(
            {
                "job_id": job_id,
                "score": score,
                "company": company,
                "title": title,
                "work_mode": work_mode,
                "location": location,
                "employment_type": employment_type,
                "matched_required": _skill_bullets(sec, "✅"),
                "unmatched_required": _skill_bullets(sec, "❌"),
                "matched_nice": _skill_bullets(sec, "⭐"),
                "tech_notes": tech_m.group(1).strip() if tech_m else None,
                "seniority": sen_m.group(1).strip() if sen_m else "",
                "salary": sal_m.group(1).strip() if sal_m else None,
                "industry": ind_m.group(1).strip() if ind_m else "",
                "url": url,
            }
        )

    return scored, filtered, date, display_date


# ── Checkbox state + MD patching ──────────────────────────────────────────────

def _read_md_state(md_path: Path) -> dict:
    """Parse current Applied/Hide checkbox state from the .md.

    Returns {job_id: {"applied": bool, "hidden": bool}}.
    """
    from job_search.pipeline.report import _parse_job_sections

    return {
        s["job_id"]: {"applied": s["applied"], "hidden": s["hidden"]}
        for s in _parse_job_sections(str(md_path))
        if s["job_id"]
    }


def _patch_md(md_path: Path, job_id: str, action: str, value: bool) -> bool:
    """Toggle a checkbox in the .md for the given job_id.

    Returns True if the job was found, False otherwise.
    """
    content = md_path.read_text(encoding="utf-8")

    url_fragment = f"linkedin.com/jobs/view/{job_id}/"
    pos = content.find(url_fragment)
    if pos == -1:
        return False

    checkbox_name = "Applied" if action == "applied" else "Hide"
    if value:
        old_box, new_box = f"- [ ] {checkbox_name}", f"- [x] {checkbox_name}"
    else:
        old_box, new_box = f"- [x] {checkbox_name}", f"- [ ] {checkbox_name}"

    window = content[pos : pos + 300]
    if old_box not in window:
        return True  # already in desired state

    md_path.write_text(
        content[:pos] + window.replace(old_box, new_box, 1) + content[pos + 300 :],
        encoding="utf-8",
    )
    return True


# ── Flask server ──────────────────────────────────────────────────────────────

def run_serve(md_path_str: str, port: int = 5757) -> None:
    from flask import Flask, jsonify, request

    md_path = Path(md_path_str).resolve()
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    app = Flask(__name__)

    @app.route("/")
    def index():
        from job_search.pipeline.html_template import HTML_TEMPLATE

        scored, filtered, date, display_date = _parse_md_to_data(md_path)
        initial_state = _read_md_state(md_path)
        payload = json.dumps(
            {
                "date": date,
                "display_date": display_date,
                "scored": scored,
                "filtered": filtered,
                "errors": [],
                "initial_state": initial_state,
            }
        ).replace("</script>", r"<\/script>")
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

    url = f"http://127.0.0.1:{port}"
    print(f"Serving {md_path.name} at {url}  (Ctrl+C to stop)")
    webbrowser.open(url)
    app.run(port=port, debug=False, use_reloader=False)
