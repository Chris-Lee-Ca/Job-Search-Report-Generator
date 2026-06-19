---
name: cover-letter
description: Generate a cover letter for a job. User provides a job title; Claude finds the job in today's daily_jobs file, looks up the description from the raw JSON, and fills in a fixed template. Trigger when user says "cover letter for X", "generate a cover letter for X", or "cover letter [job title]".
---

# Cover Letter

Generate a ready-to-send cover letter by filling in a fixed template. Only 3 fields change — the job title, company, and two small phrases. Everything else is verbatim.

## Steps

1. **Find today's daily_jobs file.**
   - Today's date in YYYY-MM-DD format.
   - File path: `output/daily_jobs_YYYY-MM-DD.md`
   - Read that file.

2. **Find the job section** matching the user-provided title.
   - Each job is a `### [score] Company — Title` heading.
   - Match on the title part (fuzzy is fine — ignore case, partial match OK).
   - If multiple matches, list them and ask the user to clarify.
   - If no match, say so and stop.

3. **Extract from the matched section:**
   - Job title (exact text after `—` in the heading)
   - Company name (exact text between `[score]` and `—`)
   - LinkedIn URL → job ID (the number in `/jobs/view/NUMBER/`)

4. **Load the full job description from the raw JSON.**
   - File path: `output/raw/raw_jobs_YYYY-MM-DD.json` (same date)
   - Find the entry where `"id"` matches the job ID.
   - Extract the `"description"` field.
   - If the raw file doesn't exist or the job isn't found, proceed with just title + company (skip tech/focus adjustments and use the template defaults).

5. **Fill in the template** with exactly these substitutions:

   | Placeholder | What to put |
   |---|---|
   | `[TITLE]` | Exact job title from the heading |
   | `[COMPANY]` | Exact company name from the heading |
   | `[ROLE_TYPE]` | One word describing the role's focus based on the job description: `backend` for systems, infrastructure, distributed, platform, DevOps, data, or API-heavy roles; `frontend` for UI/frontend-heavy roles; `full-stack` for mixed or unclear roles. |
   | `[TECH_LIST]` | 4-5 technologies from the resume that match this job's stack. For backend roles, drop React and TypeScript if they are not core to the job — include only what the role actually uses. For frontend or full-stack roles, always include React and TypeScript. Put the job's primary tech first. Use only technologies the candidate actually has. |
   | `[EXPERIENCE_HIGHLIGHT]` | One sentence describing Arctic Wolf work, tuned to the role type. Use exactly one of these — do not paraphrase: **backend:** `In my recent role at Arctic Wolf, I contributed to the development of internal platforms and tooling built on Go and Backstage, where I worked on CI/CD pipeline features, platform automation, and developer workflow improvements.` **frontend or full-stack:** `In my recent role at Arctic Wolf, I contributed to the development of an internal developer portal built on Backstage, where I worked on custom React and TypeScript plugins, platform tooling, and developer workflow improvements.` |
   | `[FOCUS_PHRASE]` | 2-3 short noun phrases drawn from the job description that describe what the role involves. Keep it generic — no jargon, no buzzwords. Example: "the combination of backend API work, cross-team collaboration, and product-focused development" |

6. **Generate a PDF** of the filled letter and save it to `output/cover_letters/cover_letter_COMPANY_YYYY-MM-DD.pdf` (use today's date, replace spaces in company name with underscores).
   - Use Python with `fpdf2` to generate the PDF. Install it if not available: `pip install fpdf2`.
   - Use the script template below. Fill in the letter text before running it.
   - After saving, tell the user the file path.

```python
from fpdf import FPDF

letter_text = """[FILLED LETTER TEXT HERE]"""

pdf = FPDF(format="Letter")
pdf.add_page()
pdf.set_margins(25.4, 25.4, 25.4)  # 1-inch margins
pdf.set_auto_page_break(auto=True, margin=25.4)
pdf.set_font("Helvetica", size=11)
pdf.set_line_height(1.5)

for para in letter_text.strip().split("\n"):
    para = para.strip()
    if para:
        pdf.multi_cell(0, 7, para)
        pdf.ln(4)
    else:
        pdf.ln(4)

pdf.output("output/cover_letters/cover_letter_COMPANY_DATE.pdf")
```

7. **Also output the filled letter** as plain text inside a plain code block (triple backticks, no language tag) so the user can copy it cleanly.

## Template

Use this verbatim — change only the 4 placeholders above.

```
Dear Hiring Manager,
I am writing to express my interest in the [TITLE] position at [COMPANY]. With over 4 years of experience in [ROLE_TYPE] software development, I have worked on a range of web applications and internal platforms using technologies including [TECH_LIST].
[EXPERIENCE_HIGHLIGHT] Previously, I also worked on React-based web applications and internal tools in collaborative Agile environments.
What interests me about this opportunity is [FOCUS_PHRASE]. I enjoy working closely with engineers and stakeholders to build practical and maintainable solutions, and I am always eager to learn new technologies and improve development processes.
Thank you for your time and consideration. I would welcome the opportunity to further discuss how my background and experience may be a good fit for the role.
Sincerely,
Chris Lee
```

## Rules

- Do not change any sentence outside the 4 placeholders.
- Do not use em dashes (—) inside the filled values.
- Do not use "passionate about", "excited to", "drive impact", or "deliver value".
- Keep `[TECH_LIST]` to 4-5 items max, comma-separated, ending with "and [last item]".
- Keep `[FOCUS_PHRASE]` to one readable phrase — 2-3 nouns joined with commas and "and".
