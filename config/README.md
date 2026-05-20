# config/

User-editable configuration. Edit these files to customize the pipeline for your situation.

---

## `config.json` — main pipeline settings

| Field | What to change |
|-------|---------------|
| `search_urls` | Your LinkedIn job search URLs. Get them by running a search on LinkedIn and copying the URL from the browser. Add `"remote_only": true` to also apply the Remote filter. |
| `hard_filter_criteria` | Plain-English rules the AI evaluates per job. Add, remove, or reword lines freely — no code changes needed. |
| `llm.provider` | `"claude"` or `"gemini"`. |
| `llm.model` | Model ID. Claude: `"claude-haiku-4-5-20251001"`. Gemini: `"gemini-2.0-flash"`. |
| `llm.api_key_env` | The name of the environment variable that holds your API key (set in `.env`). |
| `scoring.remote_score_bonus` | Extra points added to Remote roles after AI scoring (default `5`). |

---

## `qa_store.md` — saved Q&A answers (gitignored)

Stores your polished answers to job application questions so Claude returns them verbatim instead of regenerating. Created automatically when you first tell Claude to save an answer. See `qa_store.example.md` for the format.
