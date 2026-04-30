from __future__ import annotations

from pathlib import Path

from app.models import CandidateProfile, JobPosting, TailoredCVArtifact


def tailor_cv(profile: CandidateProfile, job: JobPosting) -> TailoredCVArtifact:
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
