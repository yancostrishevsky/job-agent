from app.db import get_connection, init_db
from app.models import JobPosting, MatchResult
from app.storage.jobs_repo import JobsRepo


def test_jobs_repo_deduplicates_by_url(tmp_path) -> None:
    conn = get_connection(tmp_path / "jobs.sqlite")
    init_db(conn)
    repo = JobsRepo(conn)
    match = MatchResult(
        job=JobPosting(
            source="dummy",
            source_label="Dummy",
            url="https://example.com/jobs/1",
            title="Junior ML Engineer",
            company="Acme",
            location="Krakow",
            level="Junior",
        ),
        deterministic_score=75,
        final_score=75,
        decision="maybe",
        matched_skills=["Python"],
        missing_skills=[],
        seniority_fit="target_level",
        location_fit="target_location",
        short_reason="good fit",
        rule_reasons=["target_level"],
    )

    assert repo.upsert_match(match) is True
    assert repo.upsert_match(match) is False
    count = conn.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
    assert count == 1
    conn.close()
