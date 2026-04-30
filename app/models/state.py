from __future__ import annotations

from typing import TypedDict

from app.models.domain import CandidateProfile, JobPosting, MatchResult, TailoredCVArtifact


class PipelineState(TypedDict, total=False):
    profile: CandidateProfile
    collected_jobs: list[JobPosting]
    normalized_jobs: list[JobPosting]
    filtered_jobs: list[JobPosting]
    matches: list[MatchResult]
    persisted_count: int
    new_matches: list[MatchResult]
    export_path: str
    selected_job_url: str | None
    tailored_artifact: TailoredCVArtifact | None
    warnings: list[str]
