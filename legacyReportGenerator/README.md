# Legacy Report Generator

A standalone, manual-URL job report tool — the original version before the automated pipeline existed. **The main pipeline (`fetch_jobs.py` → `score_filter.py` → `generate_report.py`) is the preferred approach.** This tool is kept here for occasional one-off use.

---

## What it does

1. Reads LinkedIn job URLs from `jobs.md`
2. Fetches each job page using `requests` + `BeautifulSoup`
3. Extracts: company, title, location, employment type, salary, and description summary
4. Writes a formatted Markdown report to `job_report.md`

---

## How to use

1. Paste LinkedIn job URLs into `jobs.md` — one per line or as Markdown links:

   ```markdown
   [Acme Corp — Backend Engineer](https://www.linkedin.com/jobs/view/1234567890/)
   https://www.linkedin.com/jobs/view/9876543210/
   ```

2. Run the script:

   ```bash
   python main.py
   ```

3. Open `job_report.md` for the formatted output.

---

## Dependencies

These are separate from the main pipeline's `requirements.txt`:

```bash
pip install requests beautifulsoup4
```

---

## Limitations

- **No login support** — only works on publicly visible job listings. LinkedIn increasingly requires login to view full descriptions, so this tool may return empty or partial data.
- **No AI scoring** — descriptions are summarised by keyword extraction, not by an LLM rubric.
- **No deduplication or seen-jobs tracking** — each run is independent.

For daily job searching with AI scoring, use the main pipeline instead.
