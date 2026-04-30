from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig
from app.db import get_connection, init_db
from app.matching.rules import score_job
from app.models import CandidateProfile, JobPosting
from app.sources.base import JobSource
from app.storage.jobs_repo import JobsRepo


@dataclass(frozen=True, slots=True)
class MatchedJob:
    """A job plus its match metadata for CLI presentation."""

    title: str
    company: str
    location: str
    match_score: int
    match_reason: str
    url: str
    source: str


def run_pipeline(
    profile: CandidateProfile, sources: list[JobSource], config: AppConfig
) -> list[MatchedJob]:
    """
    Fetch jobs from sources, score them, persist to SQLite, and return new matches.

    Only jobs that are both:
    - new (URL not seen before)
    - match_score >= config.match_threshold
    are returned.
    """

    conn = get_connection(config.db_path)
    try:
        init_db(conn)
        repo = JobsRepo(conn)

        new_matches: list[MatchedJob] = []
        for source in sources:
            jobs = source.fetch_jobs(profile)
            for job in jobs:
                match = score_job(job, profile)
                is_new = repo.upsert_job(job, match.match_score, match.match_reason)

                if is_new and match.match_score >= config.match_threshold:
                    new_matches.append(
                        MatchedJob(
                            title=job.title,
                            company=job.company,
                            location=job.location,
                            match_score=match.match_score,
                            match_reason=match.match_reason,
                            url=job.url,
                            source=source.source_name(),
                        )
                    )

        return new_matches
    finally:
        conn.close()

