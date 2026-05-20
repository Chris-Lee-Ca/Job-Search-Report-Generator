# Job Search Pipeline

Automates daily LinkedIn job screening and application tracking. Fetches job listings, filters and scores them using AI against your resume, and produces an EI-ready application report.

---

## Pipeline overview

```
fetch_jobs.py  →  output/raw_jobs_DATE.json
                          ↓
              score_filter.py  →  output/daily_jobs_DATE.md
                                           ↓  (user checks boxes)
                             generate_report.py  →  reports/applied_DATE.md
                                                            ↓
                                          data/seen_jobs.json  (updated)
```

| Phase | Script | Input | Output |
|-------|--------|-------|--------|
| 1 — Fetch | `fetch_jobs.py` | `config.json` search URLs | `output/raw_jobs_DATE.json` |
| 2 — Score & Filter | `score_filter.py` | raw jobs JSON + `resume.md` | `output/daily_jobs_DATE.md` |
| 3 — Report | `generate_report.py` | checked daily file | `reports/applied_DATE.md` |

---

## Phase 1 — Fetch (`fetch_jobs.py`)

Two-phase Playwright scrape of LinkedIn search results.

### Phase 1a — Card collection (code-only, no LLM)

Clicks through job cards on the search results page to collect job IDs and preview metadata (title, company, location). Saves a checkpoint to `output/job_ids_DATE.json` so you can resume detail fetching with `--from-ids` if interrupted.

**Pre-filters applied at this stage (fast, no LLM):**

| Filter | Type | Rule |
|--------|------|------|
| Blocked companies | String match | Fire Feed, Quik Hire Staffing |
| Staff-level titles | Regex | `staff engineer`, `staff developer`, etc. |
| Lead/principal titles | Regex | `lead engineer`, `principal developer`, `tech lead`, etc. |
| Non-BC Canadian cities | String match | Toronto, Calgary, Ottawa, Montreal, etc. |
| Non-Metro BC onsite | String match | Victoria, Kelowna, etc. (not remote) |
| Pure Remote (no country context) | Pass-through | Sent to LLM to decide |
| Metro Vancouver | String match | Always keep |

Jobs that fail pre-filter are discarded immediately — no detail page is fetched.

### Phase 1b — Detail fetch (code-only, no LLM)

Visits each job URL to extract the full description, company name, location, and employment type. Uses multi-strategy fallback selectors to handle LinkedIn's changing DOM layouts.

**Post-fetch processing (code-only, no LLM):**

- **French section stripped**: bilingual postings are trimmed to the English portion only before the description is stored in the JSON.

---

## Phase 2 — Score & Filter (`score_filter.py`)

Reads `output/raw_jobs_DATE.json` and passes each job to the configured LLM provider alongside your resume.

### Code-based steps (before and after LLM)

- **Deduplication**: jobs with identical (title, company, location) across multiple LinkedIn IDs are merged.
- **Remote/Hybrid bonus**: after the LLM returns a score, a configurable point bonus is added for Remote (+5) or Hybrid (+2.5) roles.

### LLM-evaluated hard filters

These criteria are defined in plain English in `config.json` and evaluated by the AI for each job. You can edit them freely without changing any code.

| Criterion |
|-----------|
| Exclude internships, co-ops, or student positions |
| Exclude staff engineer or staff developer title-level roles |
| Exclude roles that explicitly require more than 6 years of experience as a hard requirement |
| Exclude freelance positions (contract roles are acceptable) |
| Exclude onsite or hybrid roles not located in Metro Vancouver |
| Exclude remote roles where the company is based entirely outside Canada |

### LLM scoring rubric (0–100 pts)

| Tier | Weight | What it covers |
|------|--------|----------------|
| Mandatory requirements + seniority | **60 pts** | Must-have skills, min years required. Seniority mismatch or missing mandatory skill = significant deduction. If no specific skills are listed (e.g. "Software Developer" at a big-tech company), the candidate's skill set is treated as a full match. |
| Preferred / nice-to-have skills | **25 pts** | Bonus skills and experiences that are helpful but not required. |
| Title relevance | **15 pts** | How closely the job title matches the candidate's career trajectory. Least important tier. |

Additional rules:
- If the job requires a specific tech stack the candidate doesn't have (e.g. Java-only, .NET-only), score is capped at **15**.
- Remote roles get a configurable bonus (default **+5 pts**). Adjust via `scoring.remote_score_bonus` in `config.json`.

**Output:** `output/daily_jobs_DATE.md` — jobs sorted by score descending, each with a `- [ ] Applied` checkbox.

---

## Phase 3 — Report (`generate_report.py`)

After reviewing the daily file, mark jobs you applied to:

```markdown
- [x] Applied
```

Running `generate_report.py` then:
1. Parses all checked jobs from the daily file.
2. Writes an EI-ready Markdown table to `reports/applied_DATE.md`.
3. Updates `data/seen_jobs.json` with applied status and date.
4. Future runs flag previously-applied jobs with ⚠️ so you don't accidentally re-apply.

---

## Setup (one-time)

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure credentials

```bash
cp .env.example .env
```

Add your API key to `.env`:

```
ANTHROPIC_API_KEY=<your Anthropic API key>
# or for Gemini:
GEMINI_API_KEY=<your Gemini API key>
```

### 4. Log into LinkedIn (one-time)

```bash
python fetch_jobs.py --setup
```

A Chrome window opens. Log in normally, then press Enter in the terminal. Session cookies are saved to `browser_data/` and reused on every subsequent run. Re-run `--setup` when LinkedIn logs you out.

### 5. Fill in your resume

Edit `resume.md` with your background — skills, experience, and target roles. This is the single source of truth for both the scorer and the AI job assistant.

---

## Daily usage

```bash
# Run once (browser window appears briefly)
python fetch_jobs.py

# Run on a daily schedule
python fetch_jobs.py --schedule 17:00

# Resume detail fetching from a saved IDs checkpoint
python fetch_jobs.py --from-ids output/job_ids_2026-05-19.json

# Score an existing raw jobs file without re-scraping
python score_filter.py output/raw_jobs_2026-05-19.json

# Generate EI report from a checked daily file
python generate_report.py output/daily_jobs_2026-05-19.md

# Append to a running monthly log instead of a new file
python generate_report.py output/daily_jobs_2026-05-19.md --append
```

---

## Configuration reference (`config.json`)

| Key | Purpose |
|-----|---------|
| `search_urls` | LinkedIn search URLs to scrape. Each entry: `{"label": "...", "url": "...", "remote_only": true/false}` |
| `hard_filter_criteria` | Plain-English filter rules evaluated by the LLM. Edit freely — no code changes needed. |
| `llm.provider` | `"claude"` or `"gemini"` |
| `llm.model` | Model ID (e.g. `"claude-haiku-4-5-20251001"`, `"gemini-2.0-flash"`) |
| `llm.api_key_env` | Name of the environment variable holding the API key |
| `scoring.remote_score_bonus` | Extra pts added for Remote roles (default `5`) |

**Switching LLM providers:** change `provider`, `model`, and `api_key_env` in `config.json`. No code changes needed.

```json
{ "provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY" }
{ "provider": "gemini", "model": "gemini-2.0-flash",           "api_key_env": "GEMINI_API_KEY"    }
```

---

## AI job assistant

With the project open in Claude Code, you can ask job application questions in the terminal. Claude reads `resume.md` and `qa_store.md` automatically.

**Examples:**
- *"Is this job relevant to my background? [paste description]"*
- *"How should I answer 'Why do you want to work at 1Password?'"*
- *"Help me write a cover letter for this role."*

Save a polished answer for future reuse:
> *"Save this answer to 'Why 1Password'"*

Saved answers live in `qa_store.md` and are returned verbatim before Claude generates a new response.

---

## Debugging

Every scrape page saves an HTML snapshot to `output/debug/`:

| File | When to look |
|------|--------------|
| `debug_{label}_p{n}.html` | Jobs missing on page N of a search URL |
| `debug_detail_first.html` | First detail page — check selector structure |
| `debug_detail_missing_desc_{id}.html` | Job with no description extracted |

Read the actual HTML before writing new selectors — never guess.

---

## Project layout

```
├── fetch_jobs.py              Pipeline orchestrator (CLI entry point)
├── score_filter.py            AI filter + scorer → daily job checklist
├── generate_report.py         EI application report generator
├── job_providers/
│   ├── base.py                Abstract JobProvider interface
│   └── linkedin_provider.py   LinkedIn / Playwright implementation
├── providers/
│   ├── base.py                Abstract LLMProvider interface + JobAnalysis dataclass
│   ├── claude_provider.py     Anthropic Claude implementation
│   └── gemini_provider.py     Google Gemini implementation
├── config.json                Search URLs, filter rules, LLM config
├── resume.md                  Your background — read by scorer and AI assistant
├── qa_store.md                Saved Q&A answers for the AI assistant
├── browser_data/              Persistent Chrome profile from --setup (gitignored)
├── data/seen_jobs.json        Tracks all seen jobs and applied status
├── output/                    Daily job checklists + debug HTML (gitignored)
├── reports/                   EI application reports (gitignored)
├── tests/                     Pytest suite
└── legacyReportGenerator/     Original manual-URL tool (independent, see its README)
```
