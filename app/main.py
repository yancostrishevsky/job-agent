from __future__ import annotations

import json
from pathlib import Path

from app.config import load_candidate_profile, load_config
from app.pipeline import MatchedJob, run_pipeline
from app.sources.dummy import DummySource
from app.sources.greenhouse import GreenhouseSource
from app.sources.lever import LeverSource


def _format_job(job: MatchedJob) -> str:
    return "\n".join(
        [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location}",
            f"Score: {job.match_score}",
            f"Reason: {job.match_reason}",
            f"URL: {job.url}",
        ]
    )


def _export_latest_matches(repo_root: Path, new_matches: list[MatchedJob]) -> None:
    """Export only the new matches from this run to `output/latest_matches.json`."""

    export_path = repo_root / "output" / "latest_matches.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "score": job.match_score,
            "reason": job.match_reason,
            "url": job.url,
            "source": job.source,
        }
        for job in new_matches
    ]

    export_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    config = load_config()

    repo_root = Path(__file__).resolve().parent.parent
    candidate_profile_path = repo_root / "candidate_profile.json"
    try:
        profile = load_candidate_profile(candidate_profile_path)
    except RuntimeError as e:
        print(str(e))
        return

    sources = [DummySource()]
    if config.greenhouse_enabled:
        if config.greenhouse_board_tokens:
            sources.extend(
                GreenhouseSource(board_token=token)
                for token in config.greenhouse_board_tokens
            )
        else:
            print(
                "Warning: JOB_AGENT_GREENHOUSE_ENABLED is set, but no "
                "JOB_AGENT_GREENHOUSE_BOARD_TOKENS were provided."
            )

    if config.lever_enabled:
        if config.lever_handles:
            sources.extend(
                LeverSource(handle=handle)
                for handle in config.lever_handles
            )
        else:
            print(
                "Warning: JOB_AGENT_LEVER_ENABLED is set, but no "
                "JOB_AGENT_LEVER_HANDLES were provided."
            )
    new_matches = run_pipeline(profile=profile, sources=sources, config=config)

    _export_latest_matches(repo_root=repo_root, new_matches=new_matches)

    if not new_matches:
        print("No new matching jobs found.")
        return

    for job in new_matches:
        print(_format_job(job))
        print("")


if __name__ == "__main__":
    main()

