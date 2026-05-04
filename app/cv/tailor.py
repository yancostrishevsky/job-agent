from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import LLMConfig
from app.llm import OllamaClient, OllamaError
from app.models import CandidateProfile, JobPosting, TailoredCVArtifact


class TailoringSelectionPayload(BaseModel):
    selected_skills: list[str] = Field(default_factory=list)
    selected_project_names: list[str] = Field(default_factory=list)
    selected_project_bullets: dict[str, list[str]] = Field(default_factory=dict)
    selected_experience_keys: list[str] = Field(default_factory=list)
    selected_experience_bullets: dict[str, list[str]] = Field(default_factory=dict)
    selected_education: list[str] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CVTailoringResult:
    artifact: TailoredCVArtifact
    warnings: list[str] = field(default_factory=list)
    comparison_paths: list[Path] = field(default_factory=list)


def tailor_cv(
    profile: CandidateProfile,
    job: JobPosting,
    *,
    llm_config: LLMConfig | None = None,
    output_dir: Path | None = None,
    client: OllamaClient | None = None,
) -> CVTailoringResult:
    deterministic_artifact = _build_deterministic_artifact(profile, job)
    if llm_config is None or not llm_config.enabled or not llm_config.tailor_enabled:
        return CVTailoringResult(artifact=deterministic_artifact)

    runtime_client = client or OllamaClient(
        base_url=llm_config.base_url,
        timeout_seconds=llm_config.timeout_seconds,
        default_model=llm_config.model,
    )
    warnings: list[str] = []

    try:
        selection = runtime_client.generate_structured(
            model=llm_config.model,
            system_prompt=_tailoring_system_prompt(),
            user_prompt=_tailoring_user_prompt(profile, job),
            schema_model=TailoringSelectionPayload,
        )
        artifact = _build_artifact_from_selection(
            profile,
            job,
            selection,
            llm_model=llm_config.model,
        )
    except (OllamaError, ValueError) as exc:
        warnings.append(f"LLM CV tailoring skipped for {job.url}: {exc}")
        return CVTailoringResult(artifact=deterministic_artifact, warnings=warnings)

    comparison_paths: list[Path] = []
    if llm_config.comparison_enabled and output_dir is not None:
        comparison_dir = output_dir / "model_comparisons"
        comparison_dir.mkdir(parents=True, exist_ok=True)
        cached_by_model: dict[str, TailoredCVArtifact] = {llm_config.model: artifact}
        for model_name in llm_config.comparison_models:
            comparison_artifact = cached_by_model.get(model_name)
            if comparison_artifact is None:
                try:
                    comparison_selection = runtime_client.generate_structured(
                        model=model_name,
                        system_prompt=_tailoring_system_prompt(),
                        user_prompt=_tailoring_user_prompt(profile, job),
                        schema_model=TailoringSelectionPayload,
                    )
                    comparison_artifact = _build_artifact_from_selection(
                        profile,
                        job,
                        comparison_selection,
                        llm_model=model_name,
                    )
                except (OllamaError, ValueError) as exc:
                    warnings.append(f"LLM comparison tailoring skipped for {model_name}: {exc}")
                    continue
                cached_by_model[model_name] = comparison_artifact

            cv_path = comparison_dir / f"tailored_cv_{_slugify_model_name(model_name)}.md"
            cover_path = comparison_dir / f"tailored_cover_note_{_slugify_model_name(model_name)}.md"
            cv_path.write_text(comparison_artifact.tailored_cv_markdown, encoding="utf-8")
            cover_path.write_text(
                comparison_artifact.tailored_cover_note_markdown,
                encoding="utf-8",
            )
            comparison_paths.extend([cv_path, cover_path])

    return CVTailoringResult(
        artifact=artifact,
        warnings=warnings,
        comparison_paths=comparison_paths,
    )


def _build_deterministic_artifact(
    profile: CandidateProfile,
    job: JobPosting,
) -> TailoredCVArtifact:
    skill_hits = [
        skill for skill in profile.skills if skill.lower() in f"{job.title} {job.description}".lower()
    ]
    project_lines = []
    for project in profile.projects[:3]:
        project_lines.append(f"### {project.name}")
        project_lines.append(project.summary)
        for bullet in project.bullets[:3]:
            project_lines.append(f"- {bullet}")
        if project.skills:
            project_lines.append(f"- Relevant skills: {', '.join(project.skills)}")
        project_lines.append("")

    experience_lines = []
    for experience in profile.work_experience[:3]:
        experience_lines.append(f"### {experience.title} | {experience.employer}")
        if experience.start_date or experience.end_date:
            experience_lines.append(
                f"{experience.start_date or 'Unknown'} - {experience.end_date or 'Present'}"
            )
        for bullet in experience.bullets[:3]:
            experience_lines.append(f"- {bullet}")
        experience_lines.append("")

    cv_markdown = "\n".join(
        [
            f"# {profile.name}",
            "",
            profile.summary or "",
            "",
            "## Target Role",
            f"- {job.title} at {job.company}",
            f"- Location: {job.location}",
            "",
            "## Relevant Skills",
            f"- {', '.join(skill_hits or profile.skills[:8])}",
            "",
            "## Selected Projects",
            *project_lines,
            "## Experience",
            *(experience_lines or ["- Add verified work experience entries to candidate_profile.json"]),
            "## Education",
            *(f"- {entry}" for entry in profile.education),
        ]
    ).strip()

    cover_note = "\n".join(
        [
            f"# Cover Note for {job.title}",
            "",
            f"I am applying for the {job.title} role at {job.company}.",
            "This note is derived only from the provided candidate profile and does not add new experience.",
            "",
            "## Why this role fits",
            f"- The role aligns with my target domains: {', '.join(profile.target_domains[:5])}.",
            f"- Relevant verified skills: {', '.join(skill_hits or profile.skills[:6])}.",
            "",
            "## Guardrails",
            "- No employers, years of experience, or projects were invented.",
            "- Any emphasis or reordering is based only on the supplied profile data.",
            "- Future project ideas should be discussed separately, not presented as completed work.",
        ]
    ).strip()

    return TailoredCVArtifact(
        job_url=job.url,
        tailored_cv_markdown=cv_markdown,
        tailored_cover_note_markdown=cover_note,
        guardrail_notes=[
            "Only verified profile data was used.",
            "No fake employers, experience, or projects were added.",
        ],
    )


def _build_artifact_from_selection(
    profile: CandidateProfile,
    job: JobPosting,
    selection: TailoringSelectionPayload,
    *,
    llm_model: str,
) -> TailoredCVArtifact:
    projects_by_name = {project.name: project for project in profile.projects}
    experiences_by_key = {
        _experience_key(experience): experience for experience in profile.work_experience
    }

    selected_skills = _validated_subset(selection.selected_skills, profile.skills, "skills")
    selected_projects = _validated_subset(
        selection.selected_project_names,
        list(projects_by_name),
        "projects",
    )
    selected_experience_keys = _validated_subset(
        selection.selected_experience_keys,
        list(experiences_by_key),
        "work experience",
    )
    selected_education = _validated_subset(
        selection.selected_education,
        profile.education,
        "education",
    )

    project_lines: list[str] = []
    for project_name in selected_projects[:3]:
        project = projects_by_name[project_name]
        project_lines.append(f"### {project.name}")
        project_lines.append(project.summary)
        allowed_project_lines = set(project.bullets)
        allowed_project_lines.add(project.summary)
        selected_bullets = _validated_subset(
            selection.selected_project_bullets.get(project_name, []),
            list(allowed_project_lines),
            f"project bullets for {project_name}",
        ) or project.bullets[:3]
        for bullet in selected_bullets[:3]:
            if bullet == project.summary:
                continue
            project_lines.append(f"- {bullet}")
        if project.skills:
            project_lines.append(f"- Relevant skills: {', '.join(project.skills)}")
        project_lines.append("")

    experience_lines: list[str] = []
    for experience_key in selected_experience_keys[:3]:
        experience = experiences_by_key[experience_key]
        experience_lines.append(f"### {experience.title} | {experience.employer}")
        if experience.start_date or experience.end_date:
            experience_lines.append(
                f"{experience.start_date or 'Unknown'} - {experience.end_date or 'Present'}"
            )
        selected_bullets = _validated_subset(
            selection.selected_experience_bullets.get(experience_key, []),
            experience.bullets,
            f"experience bullets for {experience_key}",
        ) or experience.bullets[:3]
        for bullet in selected_bullets[:3]:
            experience_lines.append(f"- {bullet}")
        experience_lines.append("")

    chosen_skills = selected_skills[:8] or profile.skills[:8]
    chosen_project_names = selected_projects[:2] or [project.name for project in profile.projects[:2]]
    cover_note_lines = [
        f"# Cover Note for {job.title}",
        "",
        f"I am applying for the {job.title} role at {job.company}.",
        "This note uses only verified information from the candidate profile.",
        "",
        "## Why this role fits",
        f"- The role overlaps with my target domains: {', '.join(profile.target_domains[:5])}.",
        f"- Relevant verified skills: {', '.join(chosen_skills[:6])}.",
    ]
    if chosen_project_names:
        cover_note_lines.append(
            f"- Relevant verified projects I would emphasize: {', '.join(chosen_project_names)}."
        )
    cover_note_lines.extend(
        [
            "",
            "## Guardrails",
            "- No employers, years of experience, or projects were invented.",
            "- The LLM only selected and reordered verified profile facts.",
            "- If a fact was not in the profile, it was excluded.",
        ]
    )

    artifact = TailoredCVArtifact(
        job_url=job.url,
        tailored_cv_markdown="\n".join(
            [
                f"# {profile.name}",
                "",
                profile.summary or "",
                "",
                "## Target Role",
                f"- {job.title} at {job.company}",
                f"- Location: {job.location}",
                "",
                "## Relevant Skills",
                f"- {', '.join(chosen_skills)}",
                "",
                "## Selected Projects",
                *(project_lines or ["- No verified project highlights were selected."]),
                "## Experience",
                *(experience_lines or ["- Add verified work experience entries to candidate_profile.json"]),
                "## Education",
                *(f"- {entry}" for entry in (selected_education or profile.education)),
            ]
        ).strip(),
        tailored_cover_note_markdown="\n".join(cover_note_lines).strip(),
        guardrail_notes=[
            "Only verified profile data was used.",
            "No fake employers, experience, or projects were added.",
            "The LLM selected emphasis but did not author new facts.",
        ],
        llm_used=True,
        llm_model=llm_model,
    )
    return artifact


def _validated_subset(values: list[str], allowed: list[str], label: str) -> list[str]:
    allowed_set = set(allowed)
    invalid = [value for value in values if value not in allowed_set]
    if invalid:
        raise ValueError(f"LLM selected unsupported {label}: {invalid[0]}")
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _experience_key(experience) -> str:
    return f"{experience.title} | {experience.employer}"


def _tailoring_system_prompt() -> str:
    return (
        "You tailor a CV for a junior AI/ML candidate using only verified profile data. "
        "Never invent experience, projects, employers, dates, or years. "
        "Return JSON only, and only select exact strings from the provided options."
    )


def _tailoring_user_prompt(profile: CandidateProfile, job: JobPosting) -> str:
    project_options = {
        project.name: {
            "summary": project.summary,
            "bullets": project.bullets,
            "skills": project.skills,
        }
        for project in profile.projects
    }
    experience_options = {
        _experience_key(experience): {
            "dates": [experience.start_date, experience.end_date],
            "bullets": experience.bullets,
        }
        for experience in profile.work_experience
    }
    selection_space = {
        "skills": profile.skills,
        "projects": project_options,
        "work_experience": experience_options,
        "education": profile.education,
    }
    return (
        "Candidate profile JSON:\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        "Job posting JSON:\n"
        f"{job.model_dump_json(indent=2)}\n\n"
        "Allowed selection space JSON:\n"
        f"{json.dumps(selection_space, indent=2)}\n\n"
        "Choose the most relevant existing facts for this job. "
        "Return only exact strings from the allowed selection space."
    )


def write_tailored_artifact(output_dir: Path, artifact: TailoredCVArtifact) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tailored_cv.md").write_text(
        artifact.tailored_cv_markdown,
        encoding="utf-8",
    )
    (output_dir / "tailored_cover_note.md").write_text(
        artifact.tailored_cover_note_markdown,
        encoding="utf-8",
    )


def _slugify_model_name(model_name: str) -> str:
    return model_name.replace(":", "_").replace("/", "_")
