from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models import CandidateProfile, JobPosting, MatchResult

TARGET_DECISIONS = ("ignore", "maybe", "strong_match")
SENIOR_PENALTY_KEYWORDS = ("senior", "lead", "principal", "staff", "manager", "head")
ENTRY_LEVEL_KEYWORDS = ("intern", "internship", "junior", "graduate", "trainee", "entry-level")


@dataclass(frozen=True, slots=True)
class RuleMatchContext:
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    seniority_fit: str
    location_fit: str
    reasons: list[str]


def _combined_text(job: JobPosting) -> str:
    parts = [
        job.title,
        job.company,
        job.location,
        job.seniority or "",
        job.description,
        " ".join(job.metadata.values()),
    ]
    return " ".join(parts).lower()


def _contains_any(text: str, values: list[str] | tuple[str, ...]) -> list[str]:
    return [value for value in values if value.lower() in text]


def _decision_from_score(score: int) -> str:
    if score >= 80:
        return "strong_match"
    if score >= 55:
        return "maybe"
    return "ignore"


def _location_fit(job: JobPosting, profile: CandidateProfile) -> tuple[int, str]:
    location_text = job.location.lower()
    if any(target.lower() in location_text for target in profile.target_locations):
        return 18, "target_location"
    if "remote" in location_text:
        return 14, "remote"
    return 0, "outside_target"


def _seniority_fit(job: JobPosting, profile: CandidateProfile, text: str) -> tuple[int, str]:
    seniority_hits = _contains_any(text, SENIOR_PENALTY_KEYWORDS)
    if seniority_hits:
        return -45, f"penalized:{seniority_hits[0]}"

    target_levels = [level.lower() for level in profile.target_levels]
    if any(level in text for level in target_levels):
        return 24, "target_level"
    if any(keyword in text for keyword in ENTRY_LEVEL_KEYWORDS):
        return 18, "entry_level_inferred"
    return -5, "unclear_level"


def evaluate_rule_match(
    job: JobPosting,
    profile: CandidateProfile,
    recency_days: int | None = None,
) -> MatchResult:
    text = _combined_text(job)
    reasons: list[str] = []

    excluded_keywords = _contains_any(text, profile.exclude_keywords)
    if excluded_keywords:
        reason = f"excluded keyword '{excluded_keywords[0]}'"
        return MatchResult(
            job=job,
            deterministic_score=0,
            final_score=0,
            decision="ignore",
            matched_skills=[],
            missing_skills=[],
            seniority_fit="excluded",
            location_fit="unknown",
            short_reason=reason,
            rule_reasons=[reason],
            llm_used=False,
        )

    score = 25

    seniority_points, seniority_fit = _seniority_fit(job, profile, text)
    score += seniority_points
    reasons.append(f"seniority={seniority_fit}")

    location_points, location_fit = _location_fit(job, profile)
    score += location_points
    reasons.append(f"location={location_fit}")

    domain_hits = _contains_any(text, profile.target_domains)
    if domain_hits:
        score += min(20, len(set(domain_hits)) * 6)
        reasons.append(f"domains={', '.join(sorted(set(domain_hits))[:4])}")

    keyword_hits = _contains_any(text, profile.include_keywords)
    if keyword_hits:
        score += min(24, len(set(keyword_hits)) * 4)
        reasons.append(f"keywords={', '.join(sorted(set(keyword_hits))[:5])}")

    skill_hits = _contains_any(text, profile.skills)
    missing_skills = sorted(
        skill for skill in profile.skills if skill.lower() not in text
    )[:5]
    if skill_hits:
        score += min(12, len(set(skill_hits)) * 2)
        reasons.append(f"skills={', '.join(sorted(set(skill_hits))[:4])}")

    if recency_days is not None:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=recency_days)
        if job.posted_at and job.posted_at >= cutoff:
            score += 6
            reasons.append("recent_posting")
        elif job.posted_at:
            score -= 6
            reasons.append("older_posting")

    final_score = max(0, min(100, score))
    decision = _decision_from_score(final_score)
    short_reason = "; ".join(reasons[:4]) if reasons else "no strong signals"

    return MatchResult(
        job=job,
        deterministic_score=final_score,
        final_score=final_score,
        decision=decision,  # type: ignore[arg-type]
        matched_skills=sorted(set(skill_hits))[:6],
        missing_skills=missing_skills,
        seniority_fit=seniority_fit,
        location_fit=location_fit,
        short_reason=short_reason,
        rule_reasons=reasons,
        llm_used=False,
    )
