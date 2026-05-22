from __future__ import annotations

import json
from typing import List

import openai

from .base import JobAnalysis, JOB_USER_TEMPLATE, LLMProvider, RESUME_BLOCK_TEMPLATE, SYSTEM_PROMPT


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1", num_threads: int | None = None):
        self.model = model
        self.client = openai.OpenAI(base_url=base_url, api_key="ollama")
        # passed to Ollama via extra_body to cap CPU thread usage
        self._options = {"num_thread": num_threads} if num_threads else {}

    def analyze_job(
        self,
        resume: str,
        job_title: str,
        job_description: str,
        filter_criteria: List[str],
    ) -> JobAnalysis:
        criteria_text = "\n".join(f"- {c}" for c in filter_criteria)
        system_content = SYSTEM_PROMPT + "\n\n" + RESUME_BLOCK_TEMPLATE.format(resume=resume)
        user_content = JOB_USER_TEMPLATE.format(
            job_title=job_title,
            job_description=job_description,
            filter_criteria=criteria_text,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
                extra_body={"options": self._options} if self._options else {},
            )
        except openai.APIConnectionError:
            raise RuntimeError(
                "Cannot connect to Ollama. Is it running? Try: ollama serve"
            )

        raw = response.choices[0].message.content.strip()

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
