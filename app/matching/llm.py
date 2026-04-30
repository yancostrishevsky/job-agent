from __future__ import annotations

import json
from dataclasses import dataclass

import requests
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.config import LLMConfig
from app.models import CandidateProfile, MatchResult


class LLMRerankPayload(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    decision: str
    matched_skills: list[str]
    missing_skills: list[str]
    seniority_fit: str
    location_fit: str
    short_reason: str


@dataclass(slots=True)
class OptionalLLMReranker:
    config: LLMConfig

    def rerank(self, matches: list[MatchResult], profile: CandidateProfile) -> list[MatchResult]:
        if not self.config.enabled or not matches:
            return matches

        reranked: list[MatchResult] = []
        parser = PydanticOutputParser(pydantic_object=LLMRerankPayload)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You evaluate junior AI/ML jobs for a candidate in Poland. "
                    "Never invent facts. Return only JSON following the format instructions.",
                ),
                (
                    "human",
                    "Candidate profile:\n{profile}\n\n"
                    "Rule-based summary:\n{rule_summary}\n\n"
                    "Job posting:\n{job}\n\n"
                    "{format_instructions}",
                ),
            ]
        )

        for match in matches:
            try:
                message = prompt.format_messages(
                    profile=profile.model_dump_json(indent=2),
                    rule_summary=json.dumps(
                        {
                            "deterministic_score": match.deterministic_score,
                            "decision": match.decision,
                            "rule_reasons": match.rule_reasons,
                            "matched_skills": match.matched_skills,
                            "missing_skills": match.missing_skills,
                        },
                        indent=2,
                    ),
                    job=match.job.model_dump_json(indent=2),
                    format_instructions=parser.get_format_instructions(),
                )
                response_text = self._call_ollama(message[-1].content)
                payload = parser.parse(response_text)
            except Exception:
                reranked.append(match)
                continue

            reranked.append(
                match.model_copy(
                    update={
                        "final_score": payload.fit_score,
                        "decision": payload.decision,
                        "matched_skills": payload.matched_skills,
                        "missing_skills": payload.missing_skills,
                        "seniority_fit": payload.seniority_fit,
                        "location_fit": payload.location_fit,
                        "short_reason": payload.short_reason,
                        "llm_used": True,
                    }
                )
            )
        return reranked

    def _call_ollama(self, prompt: str) -> str:
        response = requests.post(
            f"{self.config.base_url.rstrip('/')}/api/generate",
            json={
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("response"), str):
            raise ValueError("Invalid LLM response payload")
        return payload["response"]
