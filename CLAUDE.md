# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## AI Job Assistant

This project includes a personal job assistant powered by Claude Code. When the user asks any question related to:

- Job fit ("Is this job relevant to my background?")
- Cover letters or application questions ("Why do you want to work at X?")
- Interview prep ("How should I answer this question?")
- Resume advice ("How should I describe this experience?")

**Always do this first:**

1. Read `config/resume.md` to understand the user's background, skills, and target roles.
2. Read `config/qa_store.md` and check if a pre-saved answer exists for this exact question or company.
   - If a saved answer exists: return it **verbatim**, do not rewrite or improve it.
   - If no saved answer: generate a response grounded in the resume content.

**Answer formatting rules:**

- Never use em dashes (—) in generated answers.
- Write like a normal person talking, not like an AI. Keep sentences short and straightforward. Avoid fancy phrasing, buzzwords, or anything that sounds polished or corporate.
- Avoid filler phrases like "concrete problem with real stakes", "passionate about", "excited to", "drive impact", "deliver value". These sound like AI wrote them.

**Salary questions:**
When the user asks about salary expectations for a specific role (e.g. "what salary should I ask for at X?"):

1. Check if the job listing already has a salary range — if so, use that as the anchor.
2. If no salary is listed, use WebSearch to look up current salary data for that company and role title (Glassdoor, Levels.fyi, LinkedIn Salary, etc.).
3. Factor in: job title and seniority level, years of experience required, company size and funding stage, and any live salary data found.
4. Give a specific CAD (or USD if the role is US-based) range the user can actually quote, with a one-line explanation of why.

- Do NOT guess without searching. Do NOT give a vague "it depends" answer.

**Saving answers:**
When the user says "save this answer", "remember this answer", or "remember this for [question]":

- Append to `config/qa_store.md` using this exact format:
  ```
  ## Q: [question or topic]
  **A:** [the answer to save]
  ```
- Confirm to the user that it has been saved.

---

## Testing standard

### Where tests live

Tests mirror the `job_search/` package structure under `tests/`:

- **Unit tests** — pure logic only; no browser, no live API, no real disk I/O.
  - `job_search/pipeline/score.py` → `tests/pipeline/test_score.py`
  - `job_search/pipeline/report.py` → `tests/pipeline/test_report.py`
  - `job_search/providers/scrapers/linkedin.py` → `tests/providers/scrapers/test_linkedin.py`
- **Integration tests** — live in `tests/integration/`. Require Playwright, live APIs, or test full pipeline flow. Marked `@pytest.mark.integration`.

### When to run what

```bash
# Default — fast unit tests, run after every change
pytest -m "not integration" -v

# Changed scraping logic — add browser tests
pytest tests/integration/test_scraper.py -v

# Full suite (includes Playwright)
pytest -v
```

### Rules

- Add a test for every bug fixed — name it after what broke.
- Test pure logic functions; skip thin wrappers (`load_config`, `load_resume`).
- Mock `build_provider`, `load_config`, and `load_resume` in pipeline integration tests.
- Do not mark a fix done until `pytest -m "not integration" -v` passes.

---

## Debugging workflow (follow this before claiming a fix is done)

1. **Run targeted tests first.** Run only the tests relevant to the changed file — the full suite is slow. Examples:
   - Changed `job_search/pipeline/fetch.py` → `pytest -m "not integration" -v`
   - Changed `job_search/pipeline/score.py` → `pytest tests/pipeline/test_score.py tests/integration/test_score_pipeline.py -v`
   - Changed `job_search/pipeline/report.py` → `pytest tests/pipeline/test_report.py tests/integration/test_report_pipeline.py -v`
   - Changed `job_search/providers/scrapers/linkedin.py` → `pytest tests/providers/scrapers/test_linkedin.py tests/integration/test_scraper.py -v`
   - Single test → `pytest tests/providers/scrapers/test_linkedin.py::test_pre_filter_non_bc_city_blocked_without_remote -v`
     Do not claim the fix is complete if tests fail.

2. **Check saved HTML when scraping is wrong.** Every search page visit writes a snapshot to `output/debug/`. When jobs are missing or fields are empty, open the relevant file:
   - Search pages: `output/debug/debug_{label}_p{n}.html`
   - First detail page fetched: `output/debug/debug_detail_first.html`
   - Jobs with missing description: `output/debug/debug_detail_missing_desc_{id}.html`
     Read the actual HTML structure before writing any new selectors — do not guess.

3. **Run the scraper to verify live behaviour.** Running `python main.py fetch` is allowed and encouraged when diagnosing scraper issues. Check the printed output (job counts per page, filtered reasons, description lengths) and the saved HTML together.

4. **Add a test for every bug fixed.** When fixing a bug, add a test case that reproduces the exact failure before the fix and passes after. This prevents regressions. The test should be named clearly after what broke (e.g. `test_non_bc_city_blocked_without_remote`).

5. **Never claim "done" without verifying.** A fix is not done until either (a) all tests pass, or (b) the live run output shows the expected result. State clearly which verification was done.

---

## Commands

```bash
# One-time LinkedIn login (saves session to browser_data/)
python main.py fetch --setup

# Fetch today's jobs from LinkedIn (run once)
python main.py fetch

# Fetch on a daily schedule at a given time
python main.py fetch --schedule 17:00

# Resume detail fetch from a saved checkpoint (if previous run was interrupted)
python main.py fetch --from-ids output/raw/job_ids_YYYY-MM-DD.json

# Score and filter today's raw jobs (auto-called by fetch, but can run standalone)
python main.py score

# Score a specific raw jobs file
python main.py score output/raw/raw_jobs_YYYY-MM-DD.json

# Open today's daily file as an interactive browser UI (Flask server on port 5757)
python main.py serve

# Open a specific daily file in the browser UI
python main.py serve output/daily_jobs_YYYY-MM-DD.md

# Open on a custom port
python main.py serve --port 8080

# Generate EI application report from a checked daily file
python main.py report output/daily_jobs_YYYY-MM-DD.md

# Append to a running monthly log instead of a new file
python main.py report output/daily_jobs_YYYY-MM-DD.md --append

# Re-score only the error jobs from a daily file (stops on first new error)
python main.py retry-errors output/daily_jobs_YYYY-MM-DD.md
```

Dependencies: `pip install -r requirements.txt` then `playwright install chromium`

---

## Architecture

The pipeline runs in this order:

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

- `config/resume.md` — user's background; read by the assistant and the scorer. Gitignored — copy from `config/resume.example.md`.
- `config/qa_store.md` — saved Q&A answers; always checked before generating new responses. Gitignored.
- `config/config.yaml` — all pipeline config with inline comments: search URLs, LLM provider, hard filter criteria, scoring, and LinkedIn-specific pre-filter settings (city lists, title patterns, blocked companies).
- `data/seen_jobs.json` — persistent record of every job ID seen and whether it was applied to or hidden.
- `data/daily_stats.json` — per-date counts of scored and applied jobs; used by `chart.py` to draw the trend chart.
- `job_search/config.py` — single shared loader for config, resume, and seen_jobs used by all pipeline modules.
- `job_search/pipeline/fetch.py` — LinkedIn scrape orchestrator (card collection + detail fetch).
- `job_search/pipeline/score.py` — AI filter + scorer; writes `output/daily_jobs_DATE.md`.
- `job_search/pipeline/serve.py` — Flask server: parses the `.md`, renders HTML on every GET `/`, and patches checkbox state on POST `/toggle`.
- `job_search/pipeline/html_template.py` — self-contained HTML/CSS/JS string embedded by `serve.py` at render time.
- `job_search/pipeline/report.py` — reads checked `.md` boxes, updates `seen_jobs.json`, writes EI report.
- `job_search/pipeline/retry_errors.py` — re-scores only the error entries in a daily file; stops on first new error.
- `job_search/pipeline/chart.py` — generates the `output/application_trend.png` bar + line chart.
- `job_search/pipeline/stats.py` — loads/saves `data/daily_stats.json`; backfills from existing daily files.
- `job_search/providers/llm/base.py` — `LLMProvider` abstract interface + `JobAnalysis` dataclass.
- `job_search/providers/llm/claude.py` — Anthropic Claude implementation.
- `job_search/providers/llm/gemini.py` — Google Gemini implementation.
- `job_search/providers/llm/ollama.py` — Ollama (local inference) implementation via OpenAI-compatible API.
- `job_search/providers/scrapers/linkedin.py` — Playwright LinkedIn scraper.
- `legacyReportGenerator/` — original single-file tool (manual URL list → formatted report); independent from this pipeline.

### LLM provider

Swap providers by editing `config/config.yaml`. Three providers are supported; no code changes needed.

```yaml
# Gemini (cloud, fast):
llm:
  provider: gemini
  model: gemini-2.5-flash
  api_key_env: GEMINI_API_KEY

# Claude (cloud):
llm:
  provider: claude
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY

# Ollama (free local inference — no API key needed):
llm:
  provider: ollama
  model: qwen2.5:14b
  base_url: http://localhost:11434/v1   # override with OLLAMA_BASE_URL env var
```

### Filtering

**Pre-filter** (code-only, before LLM, zero cost): configured in the `linkedin.pre_filter` and `linkedin.location_filter` sections of `config/config.yaml`. Controls title blocklist patterns, blocked companies, and city-based location filtering.

**Hard filter** (AI-based): The `hard_filter_criteria` list in `config/config.yaml` is passed as plain English to the LLM alongside the job description. Edit that list freely — no code changes needed.

**Experience cap** (code-enforced): `scoring.max_years` in `config/config.yaml` sets a hard ceiling on `min_years_required`. Even if the LLM doesn't filter the job, `score.py` will filter it when the extracted `min_years_required` >= `max_years`.

### Seen jobs / duplicate detection

`data/seen_jobs.json` maps job ID → `{ first_seen, title, company, applied, applied_date, skip }`.

- `job_search/pipeline/score.py` reads this on each run and skips previously applied or hidden jobs without calling the LLM (they appear in the **Filtered Out** section).
- `job_search/pipeline/report.py` writes back to this file when it processes applied and hidden checkboxes.

### Daily output format

`output/daily_jobs_DATE.md` — jobs sorted by score descending (Remote/Hybrid boosted within ±5 pts). Each job has a `- [ ] Applied` and `- [ ] Hide` checkbox. Mark `- [x] Applied` (via `serve` or directly in VS Code) and run `python main.py report` to produce the EI report.

### Environment variables (`config/.env`)

```
ANTHROPIC_API_KEY=<your Anthropic API key>   # only needed if using claude provider
GEMINI_API_KEY=<your Gemini API key>         # only needed if using gemini provider
OLLAMA_BASE_URL=http://<host>:11434/v1       # only needed to point Ollama at a remote machine
```

LinkedIn session is stored in `browser_data/` via `python main.py fetch --setup` (one-time login).

---

## Legacy tool (`legacyReportGenerator/`)

The original `main.py` is a standalone script: paste LinkedIn job URLs into `jobs.md`, run `python legacyReportGenerator/main.py`, and it fetches + formats each job into `job_report.md`. Independent of the new pipeline.
