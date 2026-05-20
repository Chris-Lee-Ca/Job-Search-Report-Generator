"""Score and filter jobs using AI analysis."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from job_search.config import load_config, load_resume, load_seen_jobs, save_seen_jobs

OUTPUT_DIR = Path("output")
RAW_DIR = OUTPUT_DIR / "raw"

WORK_MODE_EMOJI = {"Remote": "🌐", "Hybrid": "🏢", "Onsite": "🏛", "Unknown": "❓"}


def build_provider(config: dict):
    llm = config["llm"]
    provider_name = llm["provider"]
    model = llm["model"]
    api_key_env = llm.get("api_key_env", "ANTHROPIC_API_KEY")

    if provider_name == "claude":
        from job_search.providers.llm.claude import ClaudeProvider
        return ClaudeProvider(model=model, api_key_env=api_key_env)
    if provider_name == "gemini":
        from job_search.providers.llm.gemini import GeminiProvider
        return GeminiProvider(model=model, api_key_env=api_key_env)
    raise ValueError(f"Unknown provider '{provider_name}'. Supported: claude, gemini")


def _effective_score(score: int, work_mode: str, bonus: int) -> int:
    if work_mode == "Remote":
        return min(100, score + bonus)
    if work_mode == "Hybrid":
        return min(100, score + bonus // 2)
    return score


def _format_job_section(job: dict, analysis, previously_applied: bool) -> str:
    mode_emoji = WORK_MODE_EMOJI.get(analysis.work_mode, "❓")
    applied_marker = " ⚠️ PREVIOUSLY APPLIED" if previously_applied else ""

    company = job.get("company") or ""
    company_part = f"{company} " if company else ""
    header = (
        f"### [{analysis.score}] {company_part}— "
        f"{job.get('title', '?')} · {mode_emoji} {analysis.work_mode}{applied_marker}"
    )

    blocks = [header]

    meta_parts = [p for p in [job.get("location", ""), job.get("employment_type", "")] if p]
    if meta_parts:
        blocks.append(" · ".join(meta_parts))

    if analysis.matched_required_skills:
        blocks.append(f"✅ **Required:** {', '.join(analysis.matched_required_skills)}")
    if analysis.matched_nice_skills:
        blocks.append(f"⭐ **Preferred:** {', '.join(analysis.matched_nice_skills)}")

    if analysis.seniority_required and analysis.seniority_required != "Unknown":
        blocks.append(f"📊 {analysis.seniority_required}")
    if analysis.industry and analysis.industry != "Unknown":
        blocks.append(f"🏭 {analysis.industry}")

    blocks.append(f"[View on LinkedIn]({job.get('url', '')})\n\n- [ ] Applied")

    return "\n\n".join(blocks)


def run_score_filter(raw_jobs_path: str | None = None):
    import json

    config = load_config()
    filter_criteria = config.get("hard_filter_criteria", [])
    remote_bonus = config.get("scoring", {}).get("remote_score_bonus", 5)

    if raw_jobs_path is None:
        today = datetime.now().strftime("%Y-%m-%d")
        raw_jobs_path = RAW_DIR / f"raw_jobs_{today}.json"

    with open(raw_jobs_path, encoding="utf-8") as f:
        jobs = json.load(f)

    if not jobs:
        print("No jobs to process.")
        return

    # Deduplicate by (title, company, location)
    _seen_keys: dict[tuple, bool] = {}
    deduped: list[dict] = []
    for job in jobs:
        key = (
            job.get("title", "").lower().strip(),
            job.get("company", "").lower().strip(),
            job.get("location", "").lower().strip(),
        )
        if key not in _seen_keys:
            _seen_keys[key] = True
            deduped.append(job)
    removed = len(jobs) - len(deduped)
    if removed:
        print(f"Removed {removed} duplicate job(s) (same title+company, different LinkedIn IDs)")
    jobs = deduped

    resume = load_resume()
    seen = load_seen_jobs()
    provider = build_provider(config)
    today = datetime.now().strftime("%Y-%m-%d")
    display_date = datetime.now().strftime("%B %d, %Y")

    scored_jobs = []
    filtered_jobs = []
    errors = 0
    skips = 0

    print(f"Analysing {len(jobs)} jobs (provider={config['llm']['provider']}, model={config['llm']['model']})...")

    for i, job in enumerate(jobs, 1):
        job_id = job.get("id", "")
        print(f"  [{i}/{len(jobs)}] {job.get('company', '?')} — {job.get('title', '?')}", end=" ... ", flush=True)

        if not job.get("description") and not job.get("title"):
            print("SKIP (no content fetched)")
            skips += 1
            continue

        try:
            analysis = provider.analyze_job(
                resume=resume,
                job_title=job.get("title", ""),
                job_description=job.get("description", ""),
                filter_criteria=filter_criteria,
            )
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
            continue

        if job_id and job_id not in seen:
            seen[job_id] = {
                "first_seen": today,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "applied": False,
                "applied_date": None,
            }

        previously_applied = seen.get(job_id, {}).get("applied", False)

        if analysis.should_filter:
            print(f"FILTERED ({analysis.filter_reason})")
            filtered_jobs.append({
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "reason": analysis.filter_reason or "filtered",
            })
        else:
            analysis.score = _effective_score(analysis.score, analysis.work_mode, remote_bonus)
            print(f"score={analysis.score} ({analysis.work_mode})")
            scored_jobs.append((job, analysis, previously_applied))

    save_seen_jobs(seen)

    # Sort: score desc; within same 5-pt bucket: Remote > Hybrid > Onsite
    work_order = {"Remote": 0, "Hybrid": 1, "Onsite": 2, "Unknown": 3}
    scored_jobs.sort(key=lambda item: (
        -(item[1].score // 5 * 5),
        work_order.get(item[1].work_mode, 3),
    ))

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"daily_jobs_{today}.md"

    lines = [
        f"# Job Report — {display_date}",
        "",
        f"Fetched: {len(jobs)} | Filtered out: {len(filtered_jobs)} | Scored: {len(scored_jobs)}",
        "",
        "---",
        "",
    ]

    for job, analysis, previously_applied in scored_jobs:
        lines.append(_format_job_section(job, analysis, previously_applied))
        lines.append("\n---\n")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nReport → {out_path}")
    print(f"  {len(scored_jobs)} scored | {len(filtered_jobs)} AI-filtered | {errors} errors | {skips} skipped")
    if hasattr(provider, "_cache_hits"):
        total = provider._cache_hits + provider._cache_misses
        print(f"  Cache: {provider._cache_hits}/{total} hits ({provider._cache_misses} misses)")
