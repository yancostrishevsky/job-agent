from __future__ import annotations

import json
import sqlite3

from app.models import JobPosting, MatchResult


class JobsRepo:
    """Persist and de-duplicate job postings by URL, with optional source job ID support."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_match(self, match: MatchResult) -> bool:
        job = match.job
        insert_sql = """
            INSERT OR IGNORE INTO jobs (
                url,
                source,
                source_label,
                title,
                company,
                location,
                level,
                description,
                category,
                commitment,
                source_job_id,
                posted_at,
                match_score,
                final_score,
                decision,
                llm_used,
                match_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        insert_params = self._params_for_insert(job, match)

        update_sql = """
            UPDATE jobs
            SET
                source = ?,
                source_label = ?,
                title = ?,
                company = ?,
                location = ?,
                level = ?,
                description = ?,
                category = ?,
                commitment = ?,
                source_job_id = ?,
                posted_at = ?,
                match_score = ?,
                final_score = ?,
                decision = ?,
                llm_used = ?,
                match_reason = ?,
                last_seen_at = datetime('now')
            WHERE url = ?;
        """
        update_params = self._params_for_update(job, match)

        with self._conn:
            cur = self._conn.execute(insert_sql, insert_params)
            if cur.rowcount == 1:
                return True
            self._conn.execute(update_sql, update_params)
            return False

    def _params_for_insert(self, job: JobPosting, match: MatchResult) -> tuple[object, ...]:
        return (
            str(job.url),
            job.source,
            job.source_label,
            job.title,
            job.company,
            job.location,
            job.level,
            job.description,
            job.category,
            job.commitment,
            job.source_job_id,
            job.posted_at.isoformat() if job.posted_at else None,
            match.deterministic_score,
            match.final_score,
            match.decision,
            int(match.llm_used),
            self._reason_text(match),
        )

    def _params_for_update(self, job: JobPosting, match: MatchResult) -> tuple[object, ...]:
        return (
            job.source,
            job.source_label,
            job.title,
            job.company,
            job.location,
            job.level,
            job.description,
            job.category,
            job.commitment,
            job.source_job_id,
            job.posted_at.isoformat() if job.posted_at else None,
            match.deterministic_score,
            match.final_score,
            match.decision,
            int(match.llm_used),
            self._reason_text(match),
            str(job.url),
        )

    def _reason_text(self, match: MatchResult) -> str:
        payload = {
            "short_reason": match.short_reason,
            "rule_reasons": match.rule_reasons,
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "seniority_fit": match.seniority_fit,
            "location_fit": match.location_fit,
            "decision": match.decision,
        }
        return json.dumps(payload, ensure_ascii=True)
