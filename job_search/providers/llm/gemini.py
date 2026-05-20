from __future__ import annotations

import json
import os
from typing import List

from google import genai
from google.genai import types

from .base import JobAnalysis, LLMProvider

SYSTEM_PROMPT = """You are a job-fit analyst. Given a candidate's resume and a job posting, you:
1. Decide whether to hard-filter the job.
2. Score the candidate's fit 0–100 using a strict rubric.
3. Extract key facts for display.

Always respond with a single JSON object and nothing else."""

USER_PROMPT_TEMPLATE = """## Candidate Resume
{resume}

## Job Title
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
- If the job is primarily seeking a specific tech stack the candidate does not have (e.g. Java specialist, .NET specialist), cap the total score at 15.

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


class GeminiProvider(LLMProvider):
    def __init__(self, model: str, api_key_env: str = "GEMINI_API_KEY"):
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise ValueError(
                f"Environment variable {api_key_env} is not set. "
                "Get a free key at aistudio.google.com"
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            max_output_tokens=800,
        )

    def analyze_job(
        self,
        resume: str,
        job_title: str,
        job_description: str,
        filter_criteria: List[str],
    ) -> JobAnalysis:
        criteria_text = "\n".join(f"- {c}" for c in filter_criteria)
        prompt = USER_PROMPT_TEMPLATE.format(
            resume=resume,
            job_title=job_title,
            job_description=job_description,
            filter_criteria=criteria_text,
        )

        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config,
        )

        raw = response.text.strip()

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
