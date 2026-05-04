from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import (
    RuntimeConfig,
    load_candidate_profile,
    load_runtime_config,
    load_source_definitions,
)
from app.models import MatchResult
from app.sources import build_sources
from app.sources.dummy import DummySource
from app.workflows.graph import run_job_discovery_workflow


def _format_match(match: MatchResult) -> str:
    job = match.job
    return "\n".join(
        [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location}",
            f"Source: {job.source_label}",
            f"Score: {match.final_score}",
            f"Decision: {match.decision}",
            f"Reason: {match.short_reason}",
            f"URL: {job.url}",
        ]
    )


def _export_latest_matches(config: RuntimeConfig, matches: list[MatchResult]) -> Path:
    export_path = config.output_dir / "latest_matches.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "title": match.job.title,
            "company": match.job.company,
            "location": match.job.location,
            "source": match.job.source_label,
            "score": match.final_score,
            "deterministic_score": match.deterministic_score,
            "llm_score": match.llm_score,
            "decision": match.decision,
            "reason": match.short_reason,
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "url": str(match.job.url),
            "llm_used": match.llm_used,
            "llm_model": match.llm_model,
        }
        for match in matches
    ]
    export_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return export_path


def _load_sources(config: RuntimeConfig) -> list:
    definitions = load_source_definitions(config.sources_config_path)
    sources = build_sources(definitions)
    if not sources:
        sources = [DummySource()]
    return sources


def main() -> None:
    config = load_runtime_config()
    profile = load_candidate_profile(config.candidate_profile_path)
    sources = _load_sources(config)
    state = run_job_discovery_workflow(
        profile=profile,
        config=config,
        selected_job_url=os.getenv("JOB_AGENT_SELECTED_JOB_URL"),
    )
    matches = state.get("matches", [])
    new_matches = state.get("new_matches", [])
    export_path = Path(state.get("export_path", _export_latest_matches(config, new_matches)))
    enabled_sources = ", ".join(source.source_name() for source in sources)
    print(f"Enabled sources: {enabled_sources}")
    print(
        "Summary: "
        f"sources={len(sources)}, "
        f"collected={len(state.get('collected_jobs', []))}, "
        f"shortlisted={len(matches)}, "
        f"new={len(new_matches)}"
    )
    print(f"Exported latest matches to: {export_path}")
    for warning in state.get("warnings", []):
        print(f"Warning: {warning}")

    if not new_matches:
        print("No new shortlisted jobs found.")
        return

    for match in new_matches:
        print("")
        print(_format_match(match))


if __name__ == "__main__":
    main()
