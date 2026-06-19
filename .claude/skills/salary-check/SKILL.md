---
name: salary-check
description: Research and recommend a salary range to ask for at a specific company and role. Trigger when user asks about salary expectations, what salary to ask for, or compensation for a specific role (e.g. "what salary should I ask for at X?", "what does Y pay for this role?").
---

# Salary Check

Give a specific, defensible salary range to quote — not a vague estimate.

## Steps

1. **Check the job listing first.** If the job posting already includes a salary range, use that as the anchor.

2. **Search if no salary is listed.** Use WebSearch to look up current salary data for that company and role title. Check Glassdoor, Levels.fyi, LinkedIn Salary, and similar sources.

3. **Factor in context:**
   - Job title and seniority level
   - Years of experience required
   - Company size and funding stage
   - Any live salary data found

4. **Give a specific range** in CAD (or USD if the role is US-based) that the user can actually quote, with a one-line explanation of why that range is right.

## Rules

- Do NOT guess without searching. Always run WebSearch if no salary is listed.
- Do NOT give a vague "it depends" answer.
