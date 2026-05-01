import json

from app.config import load_candidate_profile
from app.config.loader import RuntimeConfig
from app.workflows.graph import run_job_discovery_workflow


def test_workflow_smoke_creates_export(tmp_path) -> None:
    candidate_path = tmp_path / "candidate_profile.json"
    candidate_path.write_text(
        json.dumps(
            {
                "name": "Candidate",
                "target_levels": ["junior", "internship"],
                "target_locations": ["Krakow", "remote"],
                "target_domains": ["machine learning"],
                "include_keywords": ["python", "ml"],
                "exclude_keywords": ["senior"],
                "skills": ["Python", "PyTorch"],
            }
        ),
        encoding="utf-8",
    )
    sources_path = tmp_path / "sources.json"
    sources_path.write_text(json.dumps({"sources": []}), encoding="utf-8")

    config = RuntimeConfig(
        repo_root=tmp_path,
        db_path=tmp_path / "jobs.sqlite",
        output_dir=tmp_path / "output",
        candidate_profile_path=candidate_path,
        sources_config_path=sources_path,
    )
    profile = load_candidate_profile(candidate_path)
    state = run_job_discovery_workflow(profile=profile, config=config)

    assert len(state.get("matches", [])) >= 1
    assert (tmp_path / "output" / "latest_matches.json").exists()
    debug_path = tmp_path / "output" / "collected_jobs_debug.json"
    assert debug_path.exists()
    payload = json.loads(debug_path.read_text(encoding="utf-8"))
    assert len(payload) >= 1
    assert "description_preview" in payload[0]
