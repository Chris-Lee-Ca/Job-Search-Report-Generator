# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## AI Job Assistant

This project includes a personal job assistant powered by Claude Code. When the user asks any question related to:
- Job fit ("Is this job relevant to my background?")
- Cover letters or application questions ("Why do you want to work at X?")
- Interview prep ("How should I answer this question?")
- Resume advice ("How should I describe this experience?")

**Always do this first:**
1. Read `resume.md` to understand the user's background, skills, and target roles.
2. Read `config/qa_store.md` and check if a pre-saved answer exists for this exact question or company.
   - If a saved answer exists: return it **verbatim**, do not rewrite or improve it.
   - If no saved answer: generate a response grounded in the resume content.

**Saving answers:**
When the user says "save this answer", "remember this answer", or "remember this for [question]":
- Append to `config/qa_store.md` using this exact format:
  ```
  ## Q: [question or topic]
  **A:** [the answer to save]
  ```
- Confirm to the user that it has been saved.

---

## Debugging workflow (follow this before claiming a fix is done)

1. **Run targeted tests first.** Run only the tests relevant to the changed file — the full suite is slow. Examples:
   - Changed `fetch_jobs.py` → `python -m pytest tests/test_scraper.py -v`
   - Changed `score_filter.py` → `python -m pytest tests/test_score_filter.py -v`
   - Changed `generate_report.py` → `python -m pytest tests/test_generate_report.py -v`
   - Single test → `python -m pytest tests/test_scraper.py::test_pre_filter_non_bc_city_blocked_without_remote -v`
   Do not claim the fix is complete if tests fail.

2. **Check saved HTML when scraping is wrong.** Every search page visit writes a snapshot to `output/debug/`. When jobs are missing or fields are empty, open the relevant file:
   - Search pages: `output/debug/debug_{label}_p{n}.html`
   - First detail page fetched: `output/debug/debug_detail_first.html`
   - Jobs with missing description: `output/debug/debug_detail_missing_desc_{id}.html`
   Read the actual HTML structure before writing any new selectors — do not guess.

3. **Run the scraper to verify live behaviour.** Running `python fetch_jobs.py` is allowed and encouraged when diagnosing scraper issues. Check the printed output (job counts per page, filtered reasons, description lengths) and the saved HTML together.

4. **Add a test for every bug fixed.** When fixing a bug, add a test case that reproduces the exact failure before the fix and passes after. This prevents regressions. The test should be named clearly after what broke (e.g. `test_non_bc_city_blocked_without_remote`).

5. **Never claim "done" without verifying.** A fix is not done until either (a) all tests pass, or (b) the live run output shows the expected result. State clearly which verification was done.

---

## Commands

```bash
# Fetch today's jobs from LinkedIn (run once)
python fetch_jobs.py

# Fetch on a daily schedule at a given time
python fetch_jobs.py --schedule 17:00

# Score and filter today's raw jobs (auto-called by fetch_jobs.py, but can run standalone)
python score_filter.py

# Generate EI application report from a checked daily file
python generate_report.py output/daily_jobs_YYYY-MM-DD.md

# Append to a running monthly log instead of a new file
python generate_report.py output/daily_jobs_YYYY-MM-DD.md --append
```

Dependencies: `pip install playwright anthropic openai schedule` then `playwright install chromium`

---

## Architecture

The pipeline runs in this order:

```
fetch_jobs.py  →  output/raw/raw_jobs_DATE.json
                         ↓
               score_filter.py  →  output/daily_jobs_DATE.md
                                            ↓ (user checks boxes)
                              generate_report.py  →  reports/applied_DATE.md
                                                            ↓
                                              data/seen_jobs.json (updated)
```

### Key files

- `resume.md` — user's background; read by the assistant and the scorer. Gitignored — copy from `resume.example.md`.
- `config/qa_store.md` — saved Q&A answers; always checked before generating new responses. Gitignored.
- `config/config.json` — LinkedIn search URLs, plain-English hard filter criteria, LLM provider + model.
- `data/seen_jobs.json` — persistent record of every job ID seen and whether it was applied to. Used to detect previously applied jobs in future runs.
- `providers/base.py` — `LLMProvider` abstract interface + `JobAnalysis` dataclass.
- `providers/claude_provider.py` — Anthropic SDK implementation.
- `providers/openai_provider.py` — OpenAI SDK implementation.
- `legacyReportGenerator/` — original single-file tool (manual URL list → formatted report); independent from this pipeline.

### LLM provider

Swap providers by editing `config/config.json`:
```json
"llm": { "provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY" }
```
Change `provider` to `"openai"` and `model` to `"gpt-4o-mini"` for OpenAI. No code changes needed.

### Filtering

Filtering is AI-based (not keyword matching). The `hard_filter_criteria` list in `config/config.json` is passed as plain English to the LLM alongside the job description. The AI judges whether a job matches a filter criterion based on actual content. Edit that list freely — no code changes needed.

### Seen jobs / duplicate detection

`data/seen_jobs.json` maps job ID → `{ first_seen, title, company, applied, applied_date }`.
- `score_filter.py` reads this on each run and flags jobs the user has already applied to with `⚠️ PREVIOUSLY APPLIED`.
- `generate_report.py` writes back to this file when it processes applied checkboxes.

### Daily output format

`output/daily_jobs_DATE.md` — jobs sorted by score descending (Remote/Hybrid boosted within ±5 pts). Each job has a `- [ ] Applied` checkbox. Mark `- [x] Applied` and run `generate_report.py` to produce the EI report.

### Environment variables (`.env`)

```
ANTHROPIC_API_KEY=<your Anthropic API key>
OPENAI_API_KEY=<your OpenAI API key>   # only needed if using openai provider
GEMINI_API_KEY=<your Gemini API key>   # only needed if using gemini provider
```

LinkedIn session is stored in `browser_data/` via `python fetch_jobs.py --setup` (one-time login). No cookie needed in `.env`.

---

## Legacy tool (`legacyReportGenerator/`)

The original `main.py` is a standalone script: paste LinkedIn job URLs into `jobs.md`, run `python main.py`, and it fetches + formats each job into `job_report.md`. Independent of the new pipeline.
