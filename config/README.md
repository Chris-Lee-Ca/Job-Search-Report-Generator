# config/

User-editable configuration. Edit these files to customize the pipeline for your situation.

---

## `config.yaml` — main pipeline settings

The file has inline comments explaining every field. Key sections:

### General pipeline

| Field | What to change |
|-------|---------------|
| `search_urls` | Your LinkedIn job search URLs. Get them by running a search on LinkedIn and copying the URL. Add `remote_only: true` to pass all jobs through the location pre-filter. |
| `hard_filter_criteria` | Plain-English rules the AI evaluates per job. Add, remove, or reword lines freely — no code changes needed. |
| `llm.provider` | `"claude"` or `"gemini"`. |
| `llm.model` | Model ID. Claude: `"claude-haiku-4-5-20251001"`. Gemini: `"gemini-2.0-flash"`. |
| `llm.api_key_env` | Name of the environment variable holding your API key (set in `.env`). |
| `scoring.remote_score_bonus` | Extra points added to Remote roles after AI scoring (default `5`; half applied to Hybrid). |

### LinkedIn scraper (`linkedin:`)

These settings only affect the LinkedIn Playwright scraper. No code changes needed.

| Field | What to change |
|-------|---------------|
| `linkedin.pre_filter.blocked_companies` | Company names to block outright (case-insensitive substring match). |
| `linkedin.pre_filter.staff_title_pattern` | Regex blocking staff-level job titles. |
| `linkedin.pre_filter.lead_principal_title_pattern` | Regex blocking lead/principal-level job titles. |
| `linkedin.location_filter.metro_vancouver` | Cities that always pass the location pre-filter. |
| `linkedin.location_filter.blocked_non_bc_cities` | Non-BC Canadian cities that are blocked unless the role is remote. |

---

## `qa_store.md` — saved Q&A answers (gitignored)

Stores your polished answers to job application questions so Claude returns them verbatim instead of regenerating. Created automatically when you first tell Claude to save an answer. See `qa_store.example.md` for the format.
