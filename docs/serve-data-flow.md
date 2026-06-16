# How `main.py serve` Works

`main.py serve` starts a local Flask server that renders the daily markdown file as an interactive browser UI. The markdown file is the only persistent store — no separate database, no static HTML written to disk. Every browser interaction either reads or patches that single `.md` file.

---

## Data flow diagram

```
  USER RUNS: python main.py serve output/daily_jobs_DATE.md
                          │
                          ▼
              ┌─────────────────────┐
              │  serve.py           │
              │  run_serve()        │  Resolves .md path, starts Flask on :5757,
              │                     │  opens browser tab automatically.
              └────────┬────────────┘
                       │
         ┌─────────────┼──────────────────────┐
         │             │                      │
         ▼             ▼                      ▼
   GET /          GET /state           POST /toggle
   (page load)    (not used on        (button / checkbox
                   initial load)       click in browser)
         │                                    │
         ▼                                    ▼
  ┌─────────────────────┐      ┌──────────────────────────┐
  │ _parse_md_to_data() │      │ _patch_md()              │
  │                     │      │                          │
  │ Reads .md from disk │      │ Reads .md from disk,     │
  │ and splits it into  │      │ finds the job by its     │
  │ scored jobs list +  │      │ LinkedIn URL fragment,   │
  │ filtered jobs list. │      │ flips the matching       │
  └────────┬────────────┘      │ - [ ] / - [x] checkbox   │
           │                   │ within a 300-char window, │
           ▼                   │ writes .md back to disk. │
  ┌─────────────────────┐      └──────────────┬───────────┘
  │ _read_md_state()    │                     │
  │                     │                     ▼
  │ Reads .md again to  │          { "ok": true }  →  browser
  │ extract current     │          updates card CSS in place
  │ Applied/Hide state  │          (no page reload needed)
  │ per job_id.         │
  └────────┬────────────┘
           │
           ▼
  ┌─────────────────────────────────────────────┐
  │ HTML_TEMPLATE (html_template.py)            │
  │                                             │
  │ A self-contained HTML/CSS/JS string.        │
  │ serve.py injects the JSON payload into      │
  │ the __JOBS_DATA__ placeholder at render     │
  │ time. No files written to disk.             │
  └────────┬────────────────────────────────────┘
           │
           ▼
     Browser receives complete HTML page.
     JavaScript reads the embedded JSON,
     builds cards, seeds checkbox state —
     all without any further async requests.
```

---

## Request-by-request breakdown

### GET `/` — page load

1. Flask calls `_parse_md_to_data(md_path)`:
   - Reads the `.md` file.
   - Splits on `---` separators to extract each scored job section.
   - Parses heading, score, company, title, work mode, location, skill bullets, LinkedIn URL, etc.
   - Also collects the **Filtered Out** section into a separate list.
2. Flask calls `_read_md_state(md_path)`:
   - Re-reads the `.md` using `report._parse_job_sections()`.
   - Returns `{ job_id: { applied: bool, hidden: bool } }` for every job.
3. Both results are serialised to JSON and injected into `HTML_TEMPLATE` by replacing the literal string `__JOBS_DATA__`.
4. The complete HTML is returned to the browser in a single response. No further server requests are made on load.

### POST `/toggle` — Applied or Skip button

Payload: `{ "job_id": "...", "action": "applied"|"hidden", "value": true|false }`

1. Flask calls `_patch_md(md_path, job_id, action, value)`:
   - Reads the `.md` into memory.
   - Locates the job section by searching for `linkedin.com/jobs/view/{job_id}/` in the file.
   - Looks within the next 300 characters for `- [ ] Applied` (or `Hide`) and replaces it with `- [x] Applied` (or vice-versa).
   - Writes the patched content back to disk atomically (full file write).
2. Returns `{ "ok": true }`.
3. The browser updates the card's CSS class (`applied` / `skipped`) in place — no page reload.

### GET `/state` — optional re-sync

Returns the current `{ job_id: { applied, hidden } }` map. The browser does not call this automatically on load (the initial state is already embedded in the page). It is available for manual re-sync if needed (e.g. another tab made changes).

---

## Why the .md is the only file that matters

- `main.py score` **writes** `output/daily_jobs_DATE.md` — it is the authoritative record.
- `main.py serve` **reads and patches** that same file — clicking Applied in the browser is equivalent to checking the box in VS Code.
- `main.py report` **reads** the same file — it does not care whether the boxes were checked via the browser or a text editor.

This means VS Code and the browser UI stay in sync automatically: edit the `.md` in VS Code, refresh the browser and the new state is reflected; click a button in the browser, open the `.md` in VS Code and the checkbox is already there.

---

## File references

| File | Role |
|------|------|
| [job_search/pipeline/serve.py](../job_search/pipeline/serve.py) | Flask routes, `_parse_md_to_data`, `_patch_md`, `_read_md_state` |
| [job_search/pipeline/html_template.py](../job_search/pipeline/html_template.py) | Self-contained HTML/CSS/JS template string |
| [job_search/pipeline/report.py](../job_search/pipeline/report.py) | `_parse_job_sections` (shared with serve for checkbox parsing) |
| [main.py](../main.py) | `serve` Click command — resolves default path, calls `run_serve()` |
