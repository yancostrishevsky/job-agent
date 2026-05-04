from app.config.loader import LLMConfig
from app.matching.llm import LLMRerankPayload, OptionalLLMReranker
from app.models import CandidateProfile, JobPosting, MatchResult


class FakeRerankClient:
    def __init__(self, payload: LLMRerankPayload | None = None, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    def generate_structured(self, **kwargs):
        if self.fail:
            from app.llm import OllamaUnavailableError

            raise OllamaUnavailableError("offline")
        assert self.payload is not None
        return self.payload


def _build_profile() -> CandidateProfile:
    return CandidateProfile(
        name="Candidate",
        target_levels=["junior", "internship"],
        target_locations=["Krakow", "remote"],
        target_domains=["machine learning", "AI"],
        include_keywords=["python", "ml"],
        exclude_keywords=["senior"],
        skills=["Python", "PyTorch", "SQL"],
    )


def _build_match(score: int = 70) -> MatchResult:
    return MatchResult(
        job=JobPosting(
            source="dummy",
            source_label="Dummy",
            url="https://example.com/jobs/1",
            title="Junior ML Engineer",
            company="Example",
            location="Krakow",
            description="Python and ML work",
        ),
        deterministic_score=score,
        final_score=score,
        decision="maybe",
        matched_skills=["Python"],
        missing_skills=["PyTorch"],
        seniority_fit="target_level",
        location_fit="target_location",
        short_reason="deterministic reason",
        rule_reasons=["keywords=python"],
    )


def test_reranker_blends_scores_and_marks_llm_usage(tmp_path) -> None:
    reranker = OptionalLLMReranker(
        config=LLMConfig(enabled=True, model="qwen3:4b", rerank_top_k=1),
        client=FakeRerankClient(
            payload=LLMRerankPayload(
                fit_score=90,
                decision="strong_match",
                matched_skills=["Python", "PyTorch"],
                missing_skills=["TensorFlow"],
                seniority_fit="target_level",
                location_fit="target_location",
                short_reason="Great semantic fit",
            )
        ),
    )

    result = reranker.rerank([_build_match(score=70)], _build_profile(), output_dir=tmp_path)

    assert len(result.matches) == 1
    assert result.matches[0].final_score == 77
    assert result.matches[0].llm_used is True
    assert result.matches[0].llm_model == "qwen3:4b"
    assert "llm=Great semantic fit" in result.matches[0].short_reason


def test_reranker_falls_back_when_ollama_is_unavailable(tmp_path) -> None:
    original = _build_match(score=68)
    reranker = OptionalLLMReranker(
        config=LLMConfig(enabled=True, model="qwen3:4b", rerank_top_k=1),
        client=FakeRerankClient(fail=True),
    )

    result = reranker.rerank([original], _build_profile(), output_dir=tmp_path)

    assert result.matches[0].final_score == 68
    assert result.matches[0].llm_used is False
    assert result.warnings
