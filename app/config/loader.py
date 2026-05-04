from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.models import CandidateProfile


class LLMConfig(BaseModel):
    enabled: bool = False
    provider: str = "ollama"
    model: str = "qwen3:4b"
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 30.0
    rerank_enabled: bool = True
    tailor_enabled: bool = True
    rerank_top_k: int = 10
    comparison_enabled: bool = False
    comparison_models: list[str] = Field(
        default_factory=lambda: ["qwen3:4b", "qwen3:8b", "gemma3:4b"]
    )


class SourceDefinition(BaseModel):
    type: str
    enabled: bool = True
    label: str
    config: dict[str, Any] = Field(default_factory=dict)


class RuntimeConfig(BaseModel):
    repo_root: Path
    db_path: Path
    output_dir: Path
    candidate_profile_path: Path
    sources_config_path: Path
    new_only: bool = True
    match_threshold: int = 55
    recency_days: int | None = None
    llm: LLMConfig = Field(default_factory=LLMConfig)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing required JSON file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON in {path}: {exc.msg} (line {exc.lineno}, col {exc.colno})"
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeError(f"Expected a JSON object in {path}")
    return raw


def load_candidate_profile(path: Path) -> CandidateProfile:
    raw = _load_json_file(path)
    try:
        return CandidateProfile.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid candidate profile in {path}:\n{exc}") from exc


def load_source_definitions(path: Path) -> list[SourceDefinition]:
    raw = _load_json_file(path)
    sources = raw.get("sources")
    if not isinstance(sources, list):
        raise RuntimeError(f"Expected 'sources' list in {path}")

    try:
        return [SourceDefinition.model_validate(item) for item in sources]
    except ValidationError as exc:
        raise RuntimeError(f"Invalid source definition in {path}:\n{exc}") from exc


def load_runtime_config() -> RuntimeConfig:
    repo_root = _repo_root()
    candidate_profile_path = Path(
        os.getenv("JOB_AGENT_CANDIDATE_PROFILE", repo_root / "candidate_profile.json")
    )
    sources_config_path = Path(
        os.getenv("JOB_AGENT_SOURCES_CONFIG", repo_root / "sources.json")
    )
    output_dir = Path(os.getenv("JOB_AGENT_OUTPUT_DIR", repo_root / "output"))
    db_path = Path(os.getenv("JOB_AGENT_DB_PATH", repo_root / "jobs.sqlite"))

    llm_enabled = os.getenv("JOB_AGENT_LLM_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    return RuntimeConfig(
        repo_root=repo_root,
        db_path=db_path,
        output_dir=output_dir,
        candidate_profile_path=candidate_profile_path,
        sources_config_path=sources_config_path,
        new_only=os.getenv("JOB_AGENT_NEW_ONLY", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        match_threshold=int(os.getenv("JOB_AGENT_MATCH_THRESHOLD", "55")),
        recency_days=(
            int(os.getenv("JOB_AGENT_RECENCY_DAYS"))
            if os.getenv("JOB_AGENT_RECENCY_DAYS")
            else None
        ),
        llm=LLMConfig(
            enabled=llm_enabled,
            provider=os.getenv("JOB_AGENT_LLM_PROVIDER", "ollama"),
            model=os.getenv("JOB_AGENT_LLM_MODEL", "qwen3:4b"),
            base_url=os.getenv("JOB_AGENT_LLM_BASE_URL", "http://localhost:11434"),
            timeout_seconds=float(os.getenv("JOB_AGENT_LLM_TIMEOUT_SECONDS", "30")),
            rerank_enabled=os.getenv("JOB_AGENT_LLM_RERANK_ENABLED", "true").strip().lower()
            not in {"0", "false", "no", "off"},
            tailor_enabled=os.getenv("JOB_AGENT_LLM_TAILOR_ENABLED", "true").strip().lower()
            not in {"0", "false", "no", "off"},
            rerank_top_k=int(os.getenv("JOB_AGENT_LLM_RERANK_TOP_K", "10")),
            comparison_enabled=os.getenv("JOB_AGENT_LLM_COMPARISON_ENABLED", "false")
            .strip()
            .lower()
            in {"1", "true", "yes", "on"},
            comparison_models=[
                item.strip()
                for item in os.getenv(
                    "JOB_AGENT_LLM_COMPARISON_MODELS",
                    "qwen3:4b,qwen3:8b,gemma3:4b",
                ).split(",")
                if item.strip()
            ],
        ),
    )
