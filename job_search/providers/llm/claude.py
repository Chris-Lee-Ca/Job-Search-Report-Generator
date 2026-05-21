from __future__ import annotations

import json
import os
from typing import List

import anthropic

from .base import JobAnalysis, JOB_USER_TEMPLATE, LLMProvider, RESUME_BLOCK_TEMPLATE, SYSTEM_PROMPT


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
