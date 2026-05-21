from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List

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


@dataclass
class JobAnalysis:
    """Everything the LLM returns for one job: filter decision + facts + AI-assigned score."""
    should_filter: bool
    filter_reason: Optional[str]

    # Score assigned by the AI using the rubric in the prompt (0–100)
    score: int

    # Skill breakdown — candidate skills that appear in the job posting
    matched_required_skills: List[str]
    matched_nice_skills: List[str]

    seniority_required: str    # what the job requires, e.g. "mid (2–4 yrs)"
    work_mode: str             # Remote | Hybrid | Onsite | Unknown
    industry: str


class LLMProvider(ABC):
    @abstractmethod
    def analyze_job(
        self,
        resume: str,
        job_title: str,
        job_description: str,
        filter_criteria: List[str],
    ) -> JobAnalysis:
        """
        Given the candidate's resume and a job posting, return a filter decision,
        a score (0–100) using the rubric, and extracted facts for display.
        """
        pass
