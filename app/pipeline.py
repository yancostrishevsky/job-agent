from __future__ import annotations

from dataclasses import dataclass

from app.config import RuntimeConfig
from app.models import CandidateProfile, MatchResult
from app.workflows.graph import run_job_discovery_workflow


@dataclass(frozen=True, slots=True)
class PipelineResult:
    all_matches: list[MatchResult]
    new_matches: list[MatchResult]
    persisted_count: int
    source_count: int
    collected_count: int


def run_pipeline(
    profile: CandidateProfile,
    sources: list[object],
    config: RuntimeConfig,
) -> PipelineResult:
    _ = sources
    state = run_job_discovery_workflow(profile=profile, config=config)
    all_matches = state.get("matches", [])
    new_matches = state.get("new_matches", [])
    return PipelineResult(
        all_matches=all_matches,
        new_matches=new_matches,
        persisted_count=state.get("persisted_count", 0),
        source_count=0,
        collected_count=len(state.get("collected_jobs", [])),
    )
