from app.config.loader import LLMConfig
from app.cv.tailor import CVTailoringResult, TailoringSelectionPayload, tailor_cv
from app.models import CandidateProfile, CandidateProject, CandidateWorkExperience, JobPosting


class FakeTailorClient:
    def __init__(self, payload: TailoringSelectionPayload | None = None, fail: bool = False) -> None:
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
        summary="Junior ML candidate.",
        target_levels=["junior"],
        target_locations=["Krakow", "remote"],
        target_domains=["machine learning", "AI"],
        include_keywords=["python", "ml"],
        exclude_keywords=["senior"],
        skills=["Python", "PyTorch", "SQL"],
        projects=[
            CandidateProject(
                name="LLM Evaluation Pipeline",
                summary="Built an evaluation workflow.",
                bullets=["Implemented JSON validation", "Compared prompt variants"],
                skills=["Python", "LLM evaluation"],
            )
        ],
        work_experience=[
            CandidateWorkExperience(
                employer="Acme",
                title="Research Intern",
                bullets=["Prepared training data", "Evaluated model outputs"],
            )
        ],
        education=["BSc Computer Science"],
    )


def _build_job() -> JobPosting:
    return JobPosting(
        source="dummy",
        source_label="Dummy",
        url="https://example.com/jobs/1",
        title="Junior ML Engineer",
        company="Example",
        location="Krakow",
        description="Python and model evaluation",
    )


def test_tailor_cv_uses_llm_selection_when_valid(tmp_path) -> None:
    result = tailor_cv(
        _build_profile(),
        _build_job(),
        llm_config=LLMConfig(enabled=True, model="qwen3:4b"),
        output_dir=tmp_path,
        client=FakeTailorClient(
            payload=TailoringSelectionPayload(
                selected_skills=["Python", "PyTorch"],
                selected_project_names=["LLM Evaluation Pipeline"],
                selected_project_bullets={
                    "LLM Evaluation Pipeline": ["Implemented JSON validation"]
                },
                selected_experience_keys=["Research Intern | Acme"],
                selected_experience_bullets={
                    "Research Intern | Acme": ["Evaluated model outputs"]
                },
                selected_education=["BSc Computer Science"],
            )
        ),
    )

    assert isinstance(result, CVTailoringResult)
    assert result.artifact.llm_used is True
    assert result.artifact.llm_model == "qwen3:4b"
    assert "Implemented JSON validation" in result.artifact.tailored_cv_markdown


def test_tailor_cv_falls_back_on_invalid_selection(tmp_path) -> None:
    result = tailor_cv(
        _build_profile(),
        _build_job(),
        llm_config=LLMConfig(enabled=True, model="qwen3:4b"),
        output_dir=tmp_path,
        client=FakeTailorClient(
            payload=TailoringSelectionPayload(
                selected_skills=["Rust"],
                selected_project_names=[],
                selected_project_bullets={},
                selected_experience_keys=[],
                selected_experience_bullets={},
                selected_education=[],
            )
        ),
    )

    assert result.artifact.llm_used is False
    assert result.warnings
    assert "Rust" not in result.artifact.tailored_cv_markdown
