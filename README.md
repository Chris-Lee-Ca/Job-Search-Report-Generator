# Job Searcher

Automates daily LinkedIn job screening and application tracking.

## What it does

1. **Fetches** all job listings from your configured LinkedIn search URLs every day at a time you choose.
2. **Filters** jobs using an AI model that reads the hard-filter rules you define in plain English (`config.json`).
3. **Scores** each passing job 0–100 using a structured AI rubric based on your resume — mandatory requirements and seniority carry the most weight.
4. **Outputs** a ranked Markdown checklist (`output/daily_jobs_DATE.md`) you review and tick.
5. **Generates** an EI-compatible application report from the jobs you marked as applied.

---

## Setup

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

Edit `.env` and add your Gemini API key (free at [aistudio.google.com](https://aistudio.google.com)):

```
GEMINI_API_KEY=<your Gemini API key>
```

`LI_AT_COOKIE` is optional — see the LinkedIn login section below.

### 4. Log into LinkedIn (one-time setup)

Run this once to log in via a visible browser window:

```bash
python fetch_jobs.py --setup
```

A Chrome window opens. Log into LinkedIn normally, then press Enter in the terminal. All LinkedIn cookies are exported to `browser_data/linkedin_cookies.json` and loaded on every subsequent run — no manual cookie copying required.

**If the session expires** (LinkedIn logs you out after weeks/months), just run `--setup` again.

**Optional — `LI_AT_COOKIE` in `.env`:**
If you paste your `li_at` cookie here, it will be re-injected on each run as a top-up. This can recover a partially-expired session without a full `--setup` re-login, but it is not required. Get it from: Chrome DevTools → Application → Cookies → `www.linkedin.com` → `li_at`.

### 5. Fill in your resume

Edit `resume.md` with your background — skills, experience, and target roles. This file is the single source of truth for both the AI scorer and the Claude Code assistant.

---

## Daily usage

```bash
# Activate venv first
source .venv/bin/activate

# Fetch today's jobs and score them (runs once — a browser window will appear briefly)
python fetch_jobs.py

# Or run on a daily schedule (keeps process alive)
python fetch_jobs.py --schedule 17:00
```

After the run, open `output/daily_jobs_DATE.md`, review the ranked list, and check boxes for jobs you applied to:

```markdown
- [x] Applied
```

Then generate the EI report:

```bash
# New file per day
python generate_report.py output/daily_jobs_2026-05-14.md

# Or append to a running monthly log
python generate_report.py output/daily_jobs_2026-05-13.md --append
```

Report is saved to `reports/`.

---

## Scoring

Each job is scored 0–100 by the AI using a fixed rubric:

| Tier                                  | Weight  | What it covers                                                                                                                             |
| ------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Mandatory requirements + seniority    | **60%** | Must-have skills, minimum years required — the most critical tier. Missing mandatory skills or a seniority mismatch are heavily penalized. |
| Preferred / nice-to-have requirements | **25%** | Bonus skills and experiences that are helpful but not required.                                                                            |
| Title relevance                       | **15%** | How closely the job title matches your experience pattern.                                                                                 |

Additional rules:

- If the job is specifically seeking a tech stack you don't have (e.g. Java specialist, .NET specialist), the score is capped at **15** regardless.
- Remote roles receive a small configurable bonus (default +5 pts). Adjust via `scoring.remote_score_bonus` in `config.json`.

Each job card in the daily report includes a one-line AI reasoning note explaining the score.

---

## Configuration reference (`config.json`)

| Key                          | Purpose                                                          |
| ---------------------------- | ---------------------------------------------------------------- |
| `search_urls`                | LinkedIn job search URLs to scrape                               |
| `hard_filter_criteria`       | Plain-English filter rules — edit freely, no code changes needed |
| `llm.provider`               | `gemini` or `claude`                                             |
| `llm.model`                  | Model ID (e.g. `gemini-2.0-flash`, `claude-haiku-4-5-20251001`)  |
| `llm.api_key_env`            | Name of the env var holding the API key                          |
| `scoring.remote_score_bonus` | Extra pts added for Remote roles (default 5)                     |

**Switching providers:** change `provider`, `model`, and `api_key_env` in `config.json`. No code changes needed.

```json
// Gemini (default — free tier: 1,500 req/day)
"llm": { "provider": "gemini", "model": "gemini-2.0-flash", "api_key_env": "GEMINI_API_KEY" }

// Claude
"llm": { "provider": "claude", "model": "claude-haiku-4-5-20251001", "api_key_env": "ANTHROPIC_API_KEY" }
```

---

## AI job assistant

With the project open in Claude Code, you can ask job application questions directly in the terminal. Claude reads your `resume.md` and `qa_store.md` automatically.

**Examples:**

- _"Is this job relevant to my background? [paste URL or description]"_
- _"How should I answer 'Why do you want to work at 1Password?'"_
- _"Help me write a cover letter for this role."_

To save an answer so Claude always returns it verbatim:

> _"Save this answer to 'Why 1Password'"_

Saved answers live in `qa_store.md` and are checked before generating any new response.

---

## Project layout

```
├── fetch_jobs.py          LinkedIn scraper (Playwright)
├── score_filter.py        AI filter + scoring → daily job checklist
├── generate_report.py     EI application report generator
├── providers/
│   ├── base.py            LLMProvider interface + JobAnalysis dataclass
│   ├── gemini_provider.py Google Gemini implementation
│   └── claude_provider.py Anthropic Claude implementation
├── config.json            Search URLs, filter rules, LLM config
├── resume.md              Your background — read by scorer and AI assistant
├── qa_store.md            Saved Q&A answers for the AI assistant
├── browser_data/          Persistent Chrome profile from --setup (gitignored)
├── data/seen_jobs.json    Tracks all seen jobs and applied status
├── output/                Daily job checklists (gitignored)
└── reports/               EI application reports (gitignored)
```

The `legacyReportGenerator/` folder contains the original manual-URL tool and is independent of this pipeline.
