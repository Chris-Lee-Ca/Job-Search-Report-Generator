# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Testing

Tests mirror the `job_search/` package structure under `tests/`:

- `job_search/pipeline/score.py` → `tests/pipeline/test_score.py`
- `job_search/pipeline/report.py` → `tests/pipeline/test_report.py`
- `job_search/providers/scrapers/linkedin.py` → `tests/providers/scrapers/test_linkedin.py`
- Integration tests live in `tests/integration/` and are marked `@pytest.mark.integration`.

Rules:
- Add a test for every bug fixed — name it after what broke.
- Test pure logic functions; skip thin wrappers (`load_config`, `load_resume`).
- Mock `build_provider`, `load_config`, and `load_resume` in pipeline integration tests.
- A fix is not done until `pytest -m "not integration" -v` passes or the live run confirms the result — state which.

For scraper debugging steps, use `/debug-scraper`.

---

## Commands

```bash
python main.py fetch --setup           # one-time LinkedIn login
python main.py fetch                   # fetch today's jobs
python main.py fetch --schedule 17:00  # fetch on daily schedule
python main.py fetch --from-ids output/raw/job_ids_YYYY-MM-DD.json
python main.py score
python main.py score output/raw/raw_jobs_YYYY-MM-DD.json
python main.py serve
python main.py serve output/daily_jobs_YYYY-MM-DD.md
python main.py serve --port 8080
python main.py report output/daily_jobs_YYYY-MM-DD.md
python main.py report output/daily_jobs_YYYY-MM-DD.md --append
python main.py retry-errors output/daily_jobs_YYYY-MM-DD.md
```

Dependencies: `pip install -r requirements.txt` then `playwright install chromium`

---

## Architecture

```
main.py fetch  →  output/raw/raw_jobs_DATE.json
                         ↓
               main.py score  →  output/daily_jobs_DATE.md  ← single source of truth
                                          ↓
                           main.py serve  (browser UI — reads + patches .md live)
                           — or —
                           edit .md directly in VS Code
                                          ↓ (Applied / Hide boxes checked)
                            main.py report  →  reports/applied_DATE.md
                                                        ↓
                                          data/seen_jobs.json (updated)
                                          data/daily_stats.json (updated)
                                          output/application_trend.png (regenerated)
```

### Key files

- `config/config.yaml` — all pipeline config: search URLs, LLM provider, hard filter criteria, scoring, LinkedIn pre-filter settings.
- `config/resume.md` — user's background; read by the scorer and job assistant. Gitignored.
- `config/qa_store.md` — saved Q&A answers; checked before generating new responses. Gitignored.
- `data/seen_jobs.json` — every job ID seen, with applied/hidden status.
- `job_search/config.py` — shared loader for config, resume, and seen_jobs; also `add_blocked_company()` (comment-preserving text edit of `config.yaml`).
- `job_search/pipeline/fetch.py` — LinkedIn scrape orchestrator.
- `job_search/pipeline/score.py` — AI filter + scorer; writes `output/daily_jobs_DATE.md`.
- `job_search/pipeline/serve.py` — Flask server; parses `.md`, renders HTML, patches checkboxes, blacklists companies (`/blacklist`).
- `job_search/pipeline/report.py` — reads checked `.md` boxes, updates `seen_jobs.json`, writes EI report.
- `job_search/pipeline/retry_errors.py` — re-scores only error entries; stops on first new error.
- `job_search/providers/llm/base.py` — `LLMProvider` abstract interface + `JobAnalysis` dataclass.
- `job_search/providers/scrapers/linkedin.py` — Playwright LinkedIn scraper.

### Filtering

**Pre-filter** (code-only, before LLM): `linkedin.pre_filter` and `linkedin.location_filter` in `config/config.yaml` — title blocklist, blocked companies, city-based filtering. `blocked_companies` can also be added one at a time from the `serve` UI via the 🚫 Block button on a job card (hides that listing immediately, like Skip, and appends the company to `config.yaml`).
**Hard filter** (AI-based): `hard_filter_criteria` in `config/config.yaml` — plain English, edit freely, no code changes.
**Experience cap** (code-enforced): `scoring.max_years` in `config/config.yaml` — hard ceiling on `min_years_required`.

### Seen jobs

`data/seen_jobs.json` maps job ID → `{ first_seen, title, company, applied, applied_date, skip }`. `score.py` skips previously applied/hidden jobs without calling the LLM; `report.py` writes back.

### Output format

`output/daily_jobs_DATE.md` — jobs sorted by score descending, Remote/Hybrid boosted within ±5 pts. Each job has `- [ ] Applied` and `- [ ] Hide` checkboxes. Check Applied, run `report` to produce EI report.

### LLM providers

Swap providers in `config/config.yaml` under `llm:` — gemini, claude, ollama supported, no code changes needed. API keys in `config/.env`.

---

## Legacy tool

`legacyReportGenerator/main.py` — standalone script: paste LinkedIn URLs into `jobs.md`, run to get `job_report.md`. Independent of the pipeline.
