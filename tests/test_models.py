from app.models import CandidateProfile, JobPosting


def test_candidate_profile_validation_accepts_structured_lists() -> None:
    profile = CandidateProfile(
        name="Sample Candidate",
        target_levels=["junior"],
        target_locations=["Krakow"],
        target_domains=["AI"],
        include_keywords=["python"],
        exclude_keywords=["senior"],
        skills=["Python"],
    )

    assert profile.target_levels == ["junior"]
    assert profile.skills == ["Python"]


def test_job_posting_supports_legacy_level_alias() -> None:
    job = JobPosting(
        source="dummy",
        source_label="Dummy",
        url="https://example.com/job",
        title="Junior ML Engineer",
        company="Example",
        location="Krakow, Poland",
        level="Junior",
    )

    assert job.seniority == "Junior"
    assert job.level == "Junior"
