from __future__ import annotations

from dataclasses import dataclass

from app.models import CandidateProfile, JobPosting


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Result of rule-based matching."""

    match_score: int
    match_reason: str


def _lower_set(items: list[str]) -> set[str]:
    return {s.strip().lower() for s in items if s.strip()}


def score_job(job: JobPosting, profile: CandidateProfile) -> MatchResult:
    """Score a job based on the candidate profile (rule-based, no LLMs)."""

    combined_text = " ".join(
        [job.title, job.company, job.location, job.level, job.description]
    ).lower()

    exclude_hits = [kw for kw in profile.exclude_keywords if kw.lower() in combined_text]
    if exclude_hits:
        hit = exclude_hits[0]
        return MatchResult(
            match_score=0,
            match_reason=f"Excluded due to keyword '{hit}'.",
        )

    levels = _lower_set(profile.levels)
    locations = _lower_set(profile.locations)

    job_level = job.level.strip().lower()
    level_match = (
        job_level in levels
        or any(lvl in job.title.lower() for lvl in levels)
        or any(lvl in job_level for lvl in levels)
    )

    job_location = job.location.lower()
    location_match = any(loc in job_location for loc in locations)

    keyword_hits = [kw for kw in profile.include_keywords if kw.lower() in combined_text]
    domain_hits = [d for d in profile.target_domains if d.lower() in combined_text]

    level_points = 20 if level_match else 0
    location_points = 20 if location_match else 0
    keyword_points = min(50, len(set(keyword_hits)) * 5)
    domain_points = min(20, len(set(domain_hits)) * 6)

    match_score = min(100, level_points + location_points + keyword_points + domain_points)

    parts: list[str] = []
    parts.append(f"level: {'matched' if level_match else 'no'}")
    parts.append(f"location: {'matched' if location_match else 'no'}")
    if domain_hits:
        parts.append(f"domains: {', '.join(sorted(set(domain_hits)))}")
    if keyword_hits:
        # Keep it short; these lists can get long as profiles evolve.
        short_keywords = sorted(set(keyword_hits))[:6]
        parts.append(f"keywords: {', '.join(short_keywords)}")

    match_reason = "; ".join(parts)
    return MatchResult(match_score=match_score, match_reason=match_reason)

