from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.config import LLMConfig
from app.llm import OllamaClient, OllamaError
from app.models import CandidateProfile, MatchResult


class LLMRerankPayload(BaseModel):
    fit_score: int = Field(ge=0, le=100)
    decision: Literal["ignore", "maybe", "strong_match"]
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    seniority_fit: str
    location_fit: str
    short_reason: str


@dataclass(frozen=True, slots=True)
class LLMRerankResult:
    matches: list[MatchResult]
    warnings: list[str] = field(default_factory=list)
    comparison_paths: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class OptionalLLMReranker:
    config: LLMConfig
    client: OllamaClient | None = None

    def rerank(
        self,
        matches: list[MatchResult],
        profile: CandidateProfile,
        *,
        output_dir: Path | None = None,
    ) -> LLMRerankResult:
        if not self.config.enabled or not self.config.rerank_enabled or not matches:
            return LLMRerankResult(matches=matches)

        ordered = sorted(matches, key=lambda item: item.deterministic_score, reverse=True)
        rerank_subset = ordered[: self.config.rerank_top_k]
        untouched = ordered[self.config.rerank_top_k :]

        primary_matches, warnings = self._rerank_with_model(
            rerank_subset,
            profile,
            model_name=self.config.model,
        )
        combined = sorted(
            [*primary_matches, *untouched],
            key=lambda item: (item.final_score, item.deterministic_score),
            reverse=True,
        )

        comparison_paths: list[Path] = []
        if self.config.comparison_enabled and output_dir is not None:
            comparison_dir = output_dir / "model_comparisons"
            comparison_dir.mkdir(parents=True, exist_ok=True)

            cached_by_model: dict[str, list[MatchResult]] = {self.config.model: primary_matches}
            for model_name in self.config.comparison_models:
                model_matches = cached_by_model.get(model_name)
                if model_matches is None:
                    model_matches, model_warnings = self._rerank_with_model(
                        rerank_subset,
                        profile,
                        model_name=model_name,
                    )
                    warnings.extend(model_warnings)
                    cached_by_model[model_name] = model_matches
                comparison_path = comparison_dir / f"rerank_{self._slugify_model_name(model_name)}.json"
                comparison_path.write_text(
                    json.dumps(self._serialize_matches(model_matches), indent=2),
                    encoding="utf-8",
                )
                comparison_paths.append(comparison_path)

        return LLMRerankResult(
            matches=combined,
            warnings=warnings,
            comparison_paths=comparison_paths,
        )

    def _rerank_with_model(
        self,
        matches: list[MatchResult],
        profile: CandidateProfile,
        *,
        model_name: str,
    ) -> tuple[list[MatchResult], list[str]]:
        client = self.client or OllamaClient(
            base_url=self.config.base_url,
            timeout_seconds=self.config.timeout_seconds,
            default_model=self.config.model,
        )
        reranked: list[MatchResult] = []
        warnings: list[str] = []

        for match in matches:
            try:
                payload = client.generate_structured(
                    model=model_name,
                    system_prompt=self._system_prompt(),
                    user_prompt=self._user_prompt(match, profile),
                    schema_model=LLMRerankPayload,
                )
            except OllamaError as exc:
                warnings.append(f"LLM rerank skipped for {match.job.url}: {exc}")
                reranked.append(match)
                continue

            final_score = self._blend_scores(match.deterministic_score, payload.fit_score)
            final_decision = self._decision_from_score(final_score)
            reranked.append(
                match.model_copy(
                    update={
                        "final_score": final_score,
                        "decision": final_decision,
                        "matched_skills": sorted(
                            set(match.matched_skills).union(payload.matched_skills)
                        )[:8],
                        "missing_skills": sorted(set(payload.missing_skills))[:8],
                        "seniority_fit": payload.seniority_fit,
                        "location_fit": payload.location_fit,
                        "short_reason": self._merge_short_reason(match.short_reason, payload.short_reason),
                        "rule_reasons": [
                            *match.rule_reasons,
                            f"llm_model={model_name}",
                            f"llm_decision={payload.decision}",
                            f"llm_fit_score={payload.fit_score}",
                            (
                                "score_blend="
                                f"0.65*{match.deterministic_score}+0.35*{payload.fit_score}"
                            ),
                        ],
                        "llm_used": True,
                        "llm_score": payload.fit_score,
                        "llm_model": model_name,
                    }
                )
            )

        return reranked, warnings

    def _system_prompt(self) -> str:
        return (
            "You evaluate junior AI/ML jobs for a candidate in Poland. "
            "Use only the supplied profile and job posting. "
            "Never invent facts. Return JSON only."
        )

    def _user_prompt(self, match: MatchResult, profile: CandidateProfile) -> str:
        rule_summary = {
            "deterministic_score": match.deterministic_score,
            "decision": match.decision,
            "rule_reasons": match.rule_reasons,
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
        }
        return (
            "Candidate profile JSON:\n"
            f"{profile.model_dump_json(indent=2)}\n\n"
            "Rule-based match JSON:\n"
            f"{json.dumps(rule_summary, indent=2)}\n\n"
            "Job posting JSON:\n"
            f"{match.job.model_dump_json(indent=2)}\n\n"
            "Assess semantic fit after the deterministic filter has already passed. "
            "Be strict about location and seniority, and keep the explanation concise."
        )

    def _blend_scores(self, deterministic_score: int, llm_score: int) -> int:
        return max(0, min(100, round((deterministic_score * 0.65) + (llm_score * 0.35))))

    def _decision_from_score(self, score: int) -> Literal["ignore", "maybe", "strong_match"]:
        if score >= 80:
            return "strong_match"
        if score >= 55:
            return "maybe"
        return "ignore"

    def _merge_short_reason(self, deterministic_reason: str, llm_reason: str) -> str:
        if not deterministic_reason:
            return f"llm={llm_reason}"
        return f"{deterministic_reason}; llm={llm_reason}"

    def _serialize_matches(self, matches: list[MatchResult]) -> list[dict[str, object]]:
        return [
            {
                "title": match.job.title,
                "company": match.job.company,
                "location": match.job.location,
                "url": str(match.job.url),
                "deterministic_score": match.deterministic_score,
                "llm_score": match.llm_score,
                "final_score": match.final_score,
                "decision": match.decision,
                "reason": match.short_reason,
                "llm_model": match.llm_model,
            }
            for match in matches
        ]

    def _slugify_model_name(self, model_name: str) -> str:
        return model_name.replace(":", "_").replace("/", "_")
