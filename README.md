# Job Search Pipeline

Automates daily LinkedIn job screening and application tracking. Fetches job listings, filters and scores them using AI against your resume, and produces an EI-ready application report.

---

## Pipeline overview

```
main.py fetch  →  output/raw/raw_jobs_DATE.json
                          ↓
              main.py score  →  output/daily_jobs_DATE.md
                                         ↓  (user checks boxes)
                           main.py report  →  reports/applied_DATE.md
                                                          ↓
                                        data/seen_jobs.json  (updated)
```

| Phase | Command | Input | Output |
|-------|---------|-------|--------|
| 1 — Fetch | `main.py fetch` | `config/config.yaml` search URLs | `output/raw/raw_jobs_DATE.json` |
| 2 — Score & Filter | `main.py score` | raw jobs JSON + `resume.md` | `output/daily_jobs_DATE.md` |
| 3 — Report | `main.py report` | checked daily file | `reports/applied_DATE.md` |

---

## Phase 1 — Fetch (`main.py fetch`)

Two-phase Playwright scrape of LinkedIn search results.

### Phase 1a — Card collection (code-only, no LLM)

Clicks through job cards on the search results page to collect job IDs and preview metadata (title, location). Saves a checkpoint to `output/raw/job_ids_DATE.json` so you can resume detail fetching with `--from-ids` if interrupted.

> **Note:** the card preview does not expose the company name reliably. Company is only available after the detail page is fetched (Phase 1b).

**Pre-filters applied at this stage (fast, no LLM):**

All pre-filter rules are configured in the `linkedin:` section of `config/config.yaml`. No code change is needed to add/remove cities or patterns.

| Filter | Rule |
|--------|------|
| Staff-level titles | Regex. Configured in `linkedin.pre_filter.staff_title_pattern`. |
| Lead/principal titles | Regex. Configured in `linkedin.pre_filter.lead_principal_title_pattern`. |
| Non-BC Canadian cities | Substring match. Configured in `linkedin.location_filter.blocked_non_bc_cities`. |
| Non-Metro BC onsite | Not in `linkedin.location_filter.metro_vancouver` + no "remote" in location string. |
| Metro Vancouver | Always keep. Configured in `linkedin.location_filter.metro_vancouver`. |

Jobs that fail pre-filter are discarded immediately — no detail page is fetched.

### Phase 1b — Detail fetch (code-only, no LLM)

Visits each job URL to extract the full description, company name, location, and employment type. Uses multi-strategy fallback selectors to handle LinkedIn's changing DOM layouts.

**Post-fetch processing (code-only, no LLM):**

- **Blocked companies**: after the detail page is fetched and the company name is known, jobs from blocked companies are removed. Configured in `linkedin.pre_filter.blocked_companies` (case-insensitive substring match).
- **French section stripped**: bilingual postings are trimmed to the English portion only (always on, hardcoded).

---

## Phase 2 — Score & Filter (`main.py score`)

Reads `output/raw/raw_jobs_DATE.json` and passes each job to the configured LLM provider alongside your resume.

### Code-based steps (before and after LLM)

- **Deduplication**: jobs with identical (title, company, location) across multiple LinkedIn IDs are merged.
- **Remote/Hybrid bonus**: after the LLM returns a score, a configurable point bonus is added for Remote (+N) or Hybrid (+N/2) roles.

### LLM-evaluated hard filters

These criteria are defined in plain English under `hard_filter_criteria` in `config/config.yaml` and evaluated by the AI for each job. Edit freely — no code changes needed.

| Criterion |
|-----------|
| Exclude internships, co-ops, or student positions |
| Exclude staff engineer or staff developer title-level roles |
| Exclude roles that explicitly require 5+ years of experience as a hard requirement |
| Exclude freelance positions (contract roles are acceptable) |
| Exclude onsite or hybrid roles not located in Metro Vancouver |
| Exclude remote roles where the company is based entirely outside Canada |

### LLM scoring rubric (0–100 pts)

| Tier | Weight | What it covers |
|------|--------|----------------|
| Mandatory requirements + seniority | **60 pts** | Must-have skills, min years required. Seniority mismatch or missing mandatory skill = significant deduction. If no specific skills are listed, the candidate's skill set is treated as a full match. |
| Preferred / nice-to-have skills | **25 pts** | Bonus skills and experiences that are helpful but not required. |
| Title relevance | **15 pts** | How closely the job title matches the candidate's career trajectory. Least important tier. |

Additional rules:
- If the job requires a specific tech stack the candidate doesn't have (e.g. Java-only, .NET-only), score is capped at **15**.
- Remote roles get a configurable bonus (default **+5 pts**). Adjust via `scoring.remote_score_bonus` in `config/config.yaml`.

**Output:** `output/daily_jobs_DATE.md` — jobs sorted by score descending, each with a `- [ ] Applied` checkbox.

---

## Phase 3 — Report (`main.py report`)

After reviewing the daily file, mark jobs you applied to:

```markdown
- [x] Applied
```

Running `main.py report` then:
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
cp config/.env.example config/.env
```

Add your API key to `config/.env`:

```
ANTHROPIC_API_KEY=<your Anthropic API key>
# or for Gemini:
GEMINI_API_KEY=<your Gemini API key>
```

### 4. Log into LinkedIn (one-time)

```bash
python main.py fetch --setup
```

A Chrome window opens. Log in normally, then press Enter in the terminal. Session cookies are saved to `browser_data/` and reused on every subsequent run. Re-run `--setup` when LinkedIn logs you out.

### 5. Fill in your resume

```bash
cp config/resume.example.md config/resume.md
```

Edit `config/resume.md` with your background — skills, experience, and target roles. This is the single source of truth for both the scorer and the AI job assistant. `config/resume.md` is gitignored.

---

## Daily usage

```bash
# Run once (browser window appears briefly)
python main.py fetch

# Run on a daily schedule at HH:MM
python main.py fetch --schedule 17:00

# Resume detail fetching from a saved IDs checkpoint (if previous run was interrupted)
python main.py fetch --from-ids output/raw/job_ids_2026-05-19.json

# Score an existing raw jobs file without re-scraping
python main.py score output/raw/raw_jobs_2026-05-19.json

# Generate EI report from a checked daily file
python main.py report output/daily_jobs_2026-05-19.md

# Append to a running monthly log instead of a new file
python main.py report output/daily_jobs_2026-05-19.md --append
```

---

## Configuration reference (`config/config.yaml`)

The config is a single YAML file with inline comments throughout. Key sections:

| Section | Purpose |
|---------|---------|
| `search_urls` | LinkedIn search URLs to scrape. Each entry: `label`, `url`, `remote_only` |
| `hard_filter_criteria` | Plain-English AI filter rules. Edit freely — no code changes needed. |
| `llm.provider` | `"claude"` or `"gemini"` |
| `llm.model` | Model ID (e.g. `"claude-haiku-4-5-20251001"`, `"gemini-2.0-flash"`) |
| `llm.api_key_env` | Name of the environment variable holding the API key |
| `scoring.remote_score_bonus` | Extra pts added for Remote roles (default `5`) |
| `linkedin.pre_filter` | `blocked_companies` (applied after detail fetch), `staff_title_pattern`, `lead_principal_title_pattern` (applied at card stage) |
| `linkedin.location_filter` | `metro_vancouver` (always keep) and `blocked_non_bc_cities` (block unless remote) |

**Switching LLM providers:** edit the `llm:` section in `config/config.yaml`. No code changes needed.

```yaml
llm:
  provider: gemini
  model: gemini-2.0-flash
  api_key_env: GEMINI_API_KEY
```

**Running the LLM on a remote GPU (recommended for speed):** if you have a Windows machine with a dedicated NVIDIA GPU on the same network, you can run Ollama there and connect from your Mac — `qwen2.5:7b` on an RTX 4070 takes ~2–3 seconds/job vs 30–90 seconds on an M1 Mac. Change `base_url` in `config/config.yaml` to point to the Windows machine's IP. See [docs/windows-gpu-ollama.md](docs/windows-gpu-ollama.md) for the full setup guide including firewall configuration.

---

## AI job assistant

With the project open in Claude Code, you can ask job application questions in the terminal. Claude reads `config/resume.md` and `config/qa_store.md` automatically.

**Examples:**
- *"Is this job relevant to my background? [paste description]"*
- *"How should I answer 'Why do you want to work at 1Password?'"*
- *"Help me write a cover letter for this role."*

Save a polished answer for future reuse:
> *"Save this answer to 'Why 1Password'"*

Saved answers live in `config/qa_store.md` and are returned verbatim before Claude generates a new response.

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
├── main.py                        Single CLI entry point
├── job_search/
│   ├── config.py                  Shared YAML loader (config, resume, seen_jobs)
│   ├── pipeline/
│   │   ├── fetch.py               LinkedIn scrape orchestrator
│   │   ├── score.py               AI filter + scorer → daily job checklist
│   │   └── report.py              EI application report generator
│   └── providers/
│       ├── llm/
│       │   ├── base.py            LLMProvider interface + JobAnalysis dataclass
│       │   ├── claude.py          Anthropic Claude implementation
│       │   └── gemini.py          Google Gemini implementation
│       └── scrapers/
│           ├── base.py            JobProvider abstract interface
│           └── linkedin.py        LinkedIn / Playwright implementation
├── tests/
│   ├── pipeline/                  Unit tests for pipeline modules
│   ├── providers/scrapers/        Unit tests for the LinkedIn scraper
│   └── integration/               Integration tests (Playwright + mocked LLM)
├── config/
│   ├── config.yaml                All pipeline config with inline comments
│   ├── .env                       API keys (gitignored)
│   ├── .env.example               Template for .env
│   ├── resume.md                  Your background (gitignored)
│   ├── resume.example.md          Template for resume.md
│   ├── qa_store.md                Saved Q&A answers (gitignored)
│   └── qa_store.example.md        Template for qa_store.md
├── browser_data/                  Persistent Chrome profile from --setup (gitignored)
├── data/seen_jobs.json            Tracks all seen jobs and applied status
├── output/
│   ├── daily_jobs_DATE.md         Daily job checklists (gitignored)
│   ├── raw/                       Intermediate scrape artifacts (gitignored)
│   │   ├── raw_jobs_DATE.json     Full job data from detail pages
│   │   └── job_ids_DATE.json      IDs checkpoint for --from-ids resume
│   └── debug/                     HTML snapshots for debugging selectors
├── reports/                       EI application reports (gitignored)
└── legacyReportGenerator/         Original manual-URL tool (independent, see its README)
```
