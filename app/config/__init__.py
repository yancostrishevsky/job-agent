from dataclasses import dataclass, field

from app.config.loader import (
    LLMConfig,
    RuntimeConfig,
    SourceDefinition,
    load_candidate_profile,
    load_runtime_config,
    load_source_definitions,
)


@dataclass(frozen=True, slots=True)
class AppConfig:
    db_path: object
    match_threshold: int
    greenhouse_enabled: bool = False
    greenhouse_board_tokens: list[str] = field(default_factory=list)
    lever_enabled: bool = False
    lever_handles: list[str] = field(default_factory=list)


def load_config() -> AppConfig:
    runtime = load_runtime_config()
    source_definitions = load_source_definitions(runtime.sources_config_path)

    greenhouse_tokens: list[str] = []
    lever_handle_values: list[str] = []
    for source in source_definitions:
        if source.type == "greenhouse" and source.enabled:
            greenhouse_tokens.extend(source.config.get("board_tokens", []))
        if source.type == "lever" and source.enabled:
            lever_handle_values.extend(source.config.get("handles", []))

    return AppConfig(
        db_path=runtime.db_path,
        match_threshold=runtime.match_threshold,
        greenhouse_enabled=bool(greenhouse_tokens),
        greenhouse_board_tokens=greenhouse_tokens,
        lever_enabled=bool(lever_handle_values),
        lever_handles=lever_handle_values,
    )

__all__ = [
    "AppConfig",
    "LLMConfig",
    "RuntimeConfig",
    "SourceDefinition",
    "load_config",
    "load_candidate_profile",
    "load_runtime_config",
    "load_source_definitions",
]
