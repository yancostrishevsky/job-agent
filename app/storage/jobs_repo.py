from __future__ import annotations

import sqlite3

from app.models import JobPosting


class JobsRepo:
    """Persist and de-duplicate job postings by URL."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_job(
        self, job: JobPosting, match_score: int, match_reason: str
    ) -> bool:
        """
        Insert or update a job.

        Returns `True` only when the URL was not seen before (new row inserted).
        """

        insert_sql = """
            INSERT OR IGNORE INTO jobs (
                url,
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
                match_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        insert_params = (
            job.url,
            job.title,
            job.company,
            job.location,
            job.level,
            job.description,
            job.category,
            job.commitment,
            job.source_job_id,
            job.posted_at,
            match_score,
            match_reason,
        )

        update_sql = """
            UPDATE jobs
            SET
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
                match_reason = ?,
                last_seen_at = datetime('now')
            WHERE url = ?;
        """
        update_params = (
            job.title,
            job.company,
            job.location,
            job.level,
            job.description,
            job.category,
            job.commitment,
            job.source_job_id,
            job.posted_at,
            match_score,
            match_reason,
            job.url,
        )

        with self._conn:
            cur = self._conn.execute(insert_sql, insert_params)
            if cur.rowcount == 1:
                return True
            self._conn.execute(update_sql, update_params)
            return False

