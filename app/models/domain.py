from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CandidateWorkExperience(BaseModel):
    employer: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class CandidateProject(BaseModel):
    name: str
    summary: str
    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    url: str | None = None


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "Candidate"
    email: str | None = None
    location: str | None = None
    summary: str | None = None
    target_levels: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_domains: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    work_experience: list[CandidateWorkExperience] = Field(default_factory=list)
    projects: list[CandidateProject] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)

    @property
    def levels(self) -> list[str]:
        return self.target_levels

    @property
    def locations(self) -> list[str]:
        return self.target_locations

    @field_validator(
        "target_levels",
        "target_locations",
        "target_domains",
        "include_keywords",
        "exclude_keywords",
        "skills",
        "education",
        mode="before",
    )
    @classmethod
    def _ensure_string_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError("must be a list of strings")
        return value


class JobPosting(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source: str = "unknown"
    source_label: str = "Unknown Source"
    url: HttpUrl
    title: str
    company: str
    location: str
    description: str = ""
    normalized_location: str | None = None
    seniority: str | None = Field(default=None, alias="level")
    employment_type: str | None = Field(default=None, alias="commitment")
    category: str | None = None
    source_job_id: str | None = None
    posted_at: datetime | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def level(self) -> str:
        return self.seniority or "Unknown"

    @property
    def commitment(self) -> str | None:
        return self.employment_type


class MatchResult(BaseModel):
    job: JobPosting
    deterministic_score: int = Field(ge=0, le=100)
    final_score: int = Field(ge=0, le=100)
    decision: Literal["ignore", "maybe", "strong_match"]
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    seniority_fit: str
    location_fit: str
    short_reason: str
    rule_reasons: list[str] = Field(default_factory=list)
    llm_used: bool = False
    llm_score: int | None = None
    llm_model: str | None = None


class TailoredCVArtifact(BaseModel):
    job_url: HttpUrl
    tailored_cv_markdown: str
    tailored_cover_note_markdown: str
    guardrail_notes: list[str] = Field(default_factory=list)
    llm_used: bool = False
    llm_model: str | None = None
