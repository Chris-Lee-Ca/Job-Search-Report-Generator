from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List


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

    seniority_required: str         # what the job requires, e.g. "mid (2–4 yrs)"
    work_mode: str                  # Remote | Hybrid | Onsite | Unknown
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
