from __future__ import annotations

import json
import os
import time
from typing import List

from google import genai
from google.genai import types

from .base import JobAnalysis, LLMProvider

_RETRY_STATUSES = {429, 500, 503}
_MAX_RETRIES = 3
_RETRY_BACKOFF = (5, 15, 30)  # seconds between attempts

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

**Tier 1 — Mandatory Requirements + Seniority (up to 60 pts)**
How well does the candidate satisfy the hard requirements: required skills, technologies, and seniority level?
If the job is primarily seeking a specific tech stack the candidate does not have (e.g. Java specialist, .NET specialist), cap the total score at 15.

**Tier 2 — Preferred / Nice-to-Have Requirements (up to 25 pts)**
How many of the preferred or nice-to-have skills does the candidate have?

**Tier 3 — Title Relevance (up to 15 pts)**
How closely does the job title match the candidate's experience pattern and career trajectory?

**Score range guide:**
- **90–100**: Exceptional match — candidate satisfies nearly all requirements and seniority perfectly.
- **75–89**: Good match — meets most requirements with only minor gaps.
- **60–74**: Partial match — meets the core but has notable gaps or a seniority mismatch.
- **40–59**: Weak match — missing several requirements or a significant experience gap.
- **< 40**: Poor match — wrong stack or missing most requirements.

**Self-check before finalising:** Does your score fall within the correct band above? If a generic or vague posting scored above 85, or a well-matched posting scored below 60, re-evaluate.

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
            max_output_tokens=4096,
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

        last_exc: Exception | None = None
        for attempt, backoff in enumerate((*_RETRY_BACKOFF, None), 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=self._config,
                )
                break
            except Exception as e:
                last_exc = e
                code = getattr(e, "code", None) or getattr(e, "status_code", None)
                # Also catch by message for libraries that don't expose a numeric code
                msg = str(e)
                is_transient = (
                    code in _RETRY_STATUSES
                    or any(str(s) in msg for s in _RETRY_STATUSES)
                )
                if not is_transient or attempt > _MAX_RETRIES:
                    raise
                print(f"[retry {attempt}/{_MAX_RETRIES} in {backoff}s]", end=" ", flush=True)
                time.sleep(backoff)
        else:
            raise last_exc  # type: ignore[misc]

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
            unmatched_required_skills=data.get("unmatched_required_skills") or [],
            matched_nice_skills=data.get("matched_nice_skills") or [],
            min_years_required=int(data.get("min_years_required") or 0),
            seniority_required=data.get("seniority_required") or "Unknown",
            work_mode=data.get("work_mode") or "Unknown",
            industry=data.get("industry") or "Unknown",
            tech_notes=data.get("tech_notes") or None,
        )
