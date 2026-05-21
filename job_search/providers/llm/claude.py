from __future__ import annotations

import json
import os
from typing import List

import anthropic

from .base import JobAnalysis, LLMProvider

SYSTEM_PROMPT = """You are a job-fit analyst. Given a candidate's resume and a job posting, you:
1. Decide whether to hard-filter the job.
2. Score the candidate's fit 0–100 using a strict rubric.
3. Extract key facts for display.

Always respond with a single JSON object and nothing else."""

RESUME_BLOCK_TEMPLATE = """## Candidate Resume
{resume}"""

JOB_USER_TEMPLATE = """## Job Title
{job_title}

## Job Description
{job_description}

## Hard Filter Criteria
{filter_criteria}

---

## Scoring Rubric (total 100 pts)

Score the candidate using these tiers in order of importance:

**Tier 1 — Mandatory Requirements + Seniority (60 pts)**
This is the most critical tier. Evaluate:
- Does the candidate meet the hard skill requirements (must-have technologies, languages, tools)?
- Does the candidate's seniority / years of experience match what is explicitly required?
- A seniority mismatch (e.g. job requires 5+ years, candidate has 3) = significant deduction.
- A missing mandatory skill = significant deduction.
- If the job is primarily seeking a specific tech stack the candidate does not have (e.g. Java specialist, .NET specialist), set primary_tech_mismatch=true and cap the total score at 15.
- If the job does NOT list specific required technologies or skills (e.g. just "Software Developer" or "Software Engineer" with no tech stack), treat the candidate's skill set as a full match for Tier 1 hard skills and score based on title alignment and seniority only.

**Tier 2 — Preferred / Nice-to-Have Requirements (25 pts)**
- How many of the preferred or nice-to-have skills / experiences does the candidate have?

**Tier 3 — Title Relevance (15 pts)**
- How closely does the job title match the candidate's experience pattern and career trajectory?
- This is the least important tier.

---

Respond ONLY with JSON in exactly this shape:
{{
  "should_filter": <true|false>,
  "filter_reason": "<reason if filtered, else null>",
  "score": <0-100>,
  "matched_required_skills": ["skill1"],
  "matched_nice_skills": ["skill2"],
  "seniority_required": "<e.g. Mid-level (2–4 yrs)>",
  "work_mode": "<Remote|Hybrid|Onsite|Unknown>",
  "industry": "<industry name>"
}}"""


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str, api_key_env: str = "ANTHROPIC_API_KEY"):
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(f"Environment variable {api_key_env} is not set")
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
        self._cache_hits = 0
        self._cache_misses = 0

    def analyze_job(
        self,
        resume: str,
        job_title: str,
        job_description: str,
        filter_criteria: List[str],
    ) -> JobAnalysis:
        criteria_text = "\n".join(f"- {c}" for c in filter_criteria)

        # System array: static context cached as a shared prefix across all calls.
        # cache_control on the resume block covers system_prompt + resume together,
        # maximising the token count that counts toward the caching minimum threshold.
        system = [
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": RESUME_BLOCK_TEMPLATE.format(resume=resume),
                "cache_control": {"type": "ephemeral"},
            },
        ]

        # User message: job-specific content only (varies per call, never cached).
        user_content = JOB_USER_TEMPLATE.format(
            job_title=job_title,
            job_description=job_description,
            filter_criteria=criteria_text,
        )

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )

        usage = response.usage
        if getattr(usage, "cache_read_input_tokens", 0) > 0:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        data = json.loads(raw)

        return JobAnalysis(
            should_filter=bool(data.get("should_filter") or False),
            filter_reason=data.get("filter_reason"),
            score=int(data.get("score") or 0),
            matched_required_skills=data.get("matched_required_skills") or [],
            matched_nice_skills=data.get("matched_nice_skills") or [],
            seniority_required=data.get("seniority_required") or "Unknown",
            work_mode=data.get("work_mode") or "Unknown",
            industry=data.get("industry") or "Unknown",
        )
