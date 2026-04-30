from app.matching.rules import evaluate_rule_match
from app.models import CandidateProfile, JobPosting


def test_rule_matcher_penalizes_senior_roles() -> None:
    profile = CandidateProfile(
        target_levels=["junior", "internship"],
        target_locations=["Krakow", "remote"],
        target_domains=["machine learning", "NLP"],
        include_keywords=["python", "ml"],
        exclude_keywords=["principal"],
        skills=["Python", "PyTorch"],
    )
    senior_job = JobPosting(
        source="dummy",
        source_label="Dummy",
        url="https://example.com/jobs/senior",
        title="Senior Machine Learning Engineer",
        company="Acme",
        location="Remote",
        level="Senior",
        description="Python ML systems",
    )
    junior_job = JobPosting(
        source="dummy",
        source_label="Dummy",
        url="https://example.com/jobs/junior",
        title="Junior ML Engineer",
        company="Acme",
        location="Krakow, Poland",
        level="Junior",
        description="Python machine learning and NLP",
    )

    senior_match = evaluate_rule_match(senior_job, profile)
    junior_match = evaluate_rule_match(junior_job, profile)

    assert senior_match.final_score < junior_match.final_score
    assert junior_match.decision in {"maybe", "strong_match"}
