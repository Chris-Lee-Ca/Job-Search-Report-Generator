from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List

SYSTEM_PROMPT = """You are a strict job-fit analyst. Critically evaluate whether a candidate's resume matches a job posting.

Be rigorous with scoring — most jobs should NOT score above 85. Reserve 90–100 for near-perfect matches where the candidate has the exact required stack, correct seniority, AND strong nice-to-haves. When in doubt, score lower.

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

## STEP 1 — Hard Filter Check

Read each rule below and check it against the job description. If ANY rule matches, set should_filter=true and stop — do not score.

**Rule 1 — Experience requirement:**
Does the job description EXPLICITLY state a minimum year count in Requirements, Qualifications, What You'll Bring, Must Have, You Have, About You, or the main body? (e.g. "6+ years", "minimum 6 years", "at least 7 years required")
Do NOT infer years from the job title, seniority level, or typical industry norms — only use what is literally written.
If the explicit number is 6 or more → should_filter=true, filter_reason="Requires X+ years experience" (state only what the job says, never the candidate's profile).
Exception: if "6+ years" appears ONLY under "Nice to Have", "Preferred", "Bonus", or "An asset" — do NOT filter.

**Rule 2 — Job type:**
Is this an internship, co-op, student position, or freelance? → should_filter=true

**Rule 3 — Location (onsite/hybrid only):**
Is this an onsite or hybrid role? If yes, look at the job's listed office location (NOT the candidate's location).
Is the job's office located OUTSIDE Metro Vancouver (Vancouver, Burnaby, Richmond, Surrey, Coquitlam, New Westminster, North Vancouver, West Vancouver, Delta, Langley)?
If the job is onsite/hybrid AND the office is outside those cities → should_filter=true.
If the job is onsite/hybrid AND the office IS in one of those cities → do NOT filter on location.
NOTE: Remote roles from any Canadian company always PASS this check, regardless of city listed.

**Rule 4 — Company location (remote only):**
Is this a remote role where the company is based entirely outside Canada? → should_filter=true

---

## STEP 2 — Scoring (only if not filtered)

The candidate's total years of professional experience is stated in their resume Summary section — read it from there; do not recalculate from work history dates.

Score the candidate's fit 0–100. Be strict — most jobs should score 55–80. Reserve 90+ for near-perfect matches only.

**Score cap rules (apply first):**
- Specialist role (e.g. Java-only, .NET-only, mobile-only) AND candidate lacks that primary stack → score ≤ 20
- Candidate is missing 3+ required skills → score ≤ 50
- Candidate is missing 2 required skills → score ≤ 65
- Candidate is missing 1 required skill → score ≤ 78
- All required skills match → score up to 100 based on seniority + preferred skills

**Seniority adjustment (after cap):**
- Seniority matches exactly → no deduction
- Gap of 1–2 years → deduct 8–12 pts
- Gap of 3+ years → deduct 15–20 pts

**Preferred skills adjustment:**
- Has 80%+ of preferred skills → add 0–5 pts
- Has <25% of preferred skills → deduct 5 pts

**Score sanity check:**
- 90–100: All required skills + correct seniority + most preferred skills ✓
- 75–89: All required skills + 1 small gap (seniority or 1 preferred skill)
- 55–74: Missing 1–2 required skills OR notable seniority gap
- 30–54: Missing 3+ required skills OR primary stack mismatch
- 0–29: Fundamentally wrong fit

---

## STEP 3 — Extract Fields

**min_years_required**: The minimum years of professional experience the job EXPLICITLY states as a plain integer. Read the exact phrase from Requirements/Qualifications (e.g. "5+ years" → 5, "3–5 years" → 3). Set to 0 if no specific number is stated — never guess or infer from the job title or seniority level.

**seniority_required**: State the seniority level (e.g. "Junior", "Mid-level", "Senior", "Staff/Principal").
- If the job explicitly states a year range → include it exactly: "Senior (5+ yrs)"
- If NO year range is explicitly stated — you are only inferring from the title or level — append "(est.)" to make it clear this is an estimate: "Senior (est. ~5 yrs)" or just "Senior (est.)" if you can't even guess.
- NEVER write a year range without "(est.)" unless the job description literally states that number.

**matched_required_skills**: Skills listed as required in the job that the candidate HAS. Be thorough — aim for 5–10 items.

**unmatched_required_skills**: Skills listed as required in the job that the candidate DOES NOT have. List only the gaps.

**matched_nice_skills**: Preferred/nice-to-have skills from the job that the candidate has.

**salary_range**: Copy the salary/compensation range EXACTLY as written in the job description (e.g. "$90,000–$120,000 CAD", "£50k–£70k", "$70–$90/hr"). Set to null if no salary or compensation range is stated anywhere in the posting — do NOT estimate or infer.

**tech_notes**: One sentence on the tech stack focus. Examples:
- "Primarily a TypeScript/React frontend role with Node.js backend."
- "Specialist Java/Spring Boot backend role — stack flexibility is low."
- "Full-stack with flexible stack; any modern web framework is acceptable."
- "Heavy AWS/Kubernetes infrastructure focus."

---

Respond ONLY with JSON in exactly this shape:
{{
  "should_filter": <true|false>,
  "filter_reason": "<reason if filtered, else null>",
  "score": <0-100>,
  "matched_required_skills": ["skill1", "skill2"],
  "unmatched_required_skills": ["skill3"],
  "matched_nice_skills": ["skill1", "skill2"],
  "min_years_required": <integer — the minimum years of experience explicitly required; 0 if not specified>,
  "seniority_required": "<e.g. 'Senior (5+ yrs)' if stated, or 'Senior (est. ~5 yrs)' if guessed from title>",
  "salary_range": "<exact salary range from the posting, or null>",
  "work_mode": "<Remote|Hybrid|Onsite|Unknown>",
  "industry": "<industry name>",
  "tech_notes": "<one sentence about the tech stack>"
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
    unmatched_required_skills: List[str]   # required skills the candidate LACKS
    matched_nice_skills: List[str]

    min_years_required: int     # minimum years explicitly required; 0 = not specified
    seniority_required: str    # what the job requires, e.g. "mid (2–4 yrs)"
    work_mode: str             # Remote | Hybrid | Onsite | Unknown
    industry: str
    salary_range: Optional[str] = None   # exact text from posting, null if not stated
    tech_notes: Optional[str] = None


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
