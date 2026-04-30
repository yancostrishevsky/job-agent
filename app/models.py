from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    """Candidate preferences used for rule-based matching."""

    levels: list[str]
    locations: list[str]
    target_domains: list[str]
    include_keywords: list[str]
    exclude_keywords: list[str]


@dataclass(frozen=True, slots=True)
class JobPosting:
    """A single job posting returned by a JobSource adapter."""

    url: str
    title: str
    company: str
    location: str
    level: str
    description: str
    source_job_id: str | None = None
    posted_at: str | None = None
    category: str | None = None
    commitment: str | None = None

