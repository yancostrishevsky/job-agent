from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.models import CandidateProfile


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration for the job-monitoring CLI."""

    # SQLite database file.
    db_path: Path

    # Only jobs with match_score >= match_threshold are considered "matching".
    match_threshold: int = 60

    # Enable fetching jobs from Greenhouse Job Board API.
    greenhouse_enabled: bool = False
    # One or more Greenhouse board tokens (comma-separated in env).
    greenhouse_board_tokens: list[str] = field(default_factory=list)

    # Enable fetching jobs from Lever (public Postings API / feeds).
    lever_enabled: bool = False
    # One or more Lever site/company handles (comma-separated in env).
    lever_handles: list[str] = field(default_factory=list)


def load_config() -> AppConfig:
    """Load configuration from environment variables (if set)."""

    # Default to a db file inside the repo (works from `python -m app.main`).
    repo_root = Path(__file__).resolve().parent.parent
    default_db_path = repo_root / "jobs.sqlite"

    db_path_str = os.getenv("JOB_AGENT_DB_PATH")
    db_path = Path(db_path_str) if db_path_str else default_db_path

    threshold_str = os.getenv("JOB_AGENT_MATCH_THRESHOLD")
    match_threshold = int(threshold_str) if threshold_str else 60

    enabled_str = os.getenv("JOB_AGENT_GREENHOUSE_ENABLED", "false").strip().lower()
    greenhouse_enabled = enabled_str in {"1", "true", "yes", "y", "on"}

    tokens_str = os.getenv("JOB_AGENT_GREENHOUSE_BOARD_TOKENS", "").strip()
    board_tokens = [
        t.strip()
        for t in tokens_str.split(",")
        if t.strip()
    ]

    if not greenhouse_enabled:
        board_tokens = []

    enabled_str = os.getenv("JOB_AGENT_LEVER_ENABLED", "false").strip().lower()
    lever_enabled = enabled_str in {"1", "true", "yes", "y", "on"}

    handles_str = os.getenv("JOB_AGENT_LEVER_HANDLES", "").strip()
    lever_handles = [h.strip() for h in handles_str.split(",") if h.strip()]
    if not lever_enabled:
        lever_handles = []

    return AppConfig(
        db_path=db_path,
        match_threshold=match_threshold,
        greenhouse_enabled=greenhouse_enabled,
        greenhouse_board_tokens=board_tokens,
        lever_enabled=lever_enabled,
        lever_handles=lever_handles,
    )


def load_candidate_profile(profile_path: Path) -> CandidateProfile:
    """
    Load and validate the candidate profile from a local JSON file.

    Expected JSON fields:
    - target_levels
    - target_locations
    - target_domains
    - include_keywords
    - exclude_keywords
    """

    required_fields = [
        "target_levels",
        "target_locations",
        "target_domains",
        "include_keywords",
        "exclude_keywords",
    ]

    try:
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(f"Error: candidate profile file not found: {profile_path}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Error: invalid JSON in {profile_path}: {e.msg} (line {e.lineno}, col {e.colno})"
        ) from e

    if not isinstance(raw, dict):
        raise RuntimeError(f"Error: candidate profile JSON must be an object: {profile_path}")

    missing = [field for field in required_fields if field not in raw]
    if missing:
        raise RuntimeError(
            "Error: candidate profile is missing required fields: " + ", ".join(missing)
        )

    for field in required_fields:
        value = raw.get(field)
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise RuntimeError(f"Error: field '{field}' must be a list of strings")

    # Map JSON naming to our internal model.
    return CandidateProfile(
        levels=raw["target_levels"],
        locations=raw["target_locations"],
        target_domains=raw["target_domains"],
        include_keywords=raw["include_keywords"],
        exclude_keywords=raw["exclude_keywords"],
    )

