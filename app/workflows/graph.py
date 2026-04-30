from __future__ import annotations

import json
from pathlib import Path

from app.config import RuntimeConfig, load_source_definitions
from app.cv.tailor import tailor_cv, write_tailored_artifact
from app.db import get_connection, init_db
from app.matching.rules import evaluate_rule_match
from app.models import CandidateProfile, MatchResult, PipelineState
from app.sources import build_sources
from app.sources.dummy import DummySource
from app.storage.jobs_repo import JobsRepo


def collect_jobs_node(state: PipelineState, config: RuntimeConfig) -> PipelineState:
    definitions = load_source_definitions(config.sources_config_path)
    sources = build_sources(definitions) or [DummySource()]
    jobs = []
    warnings = list(state.get("warnings", []))
    for source in sources:
        try:
            jobs.extend(source.fetch_jobs())
        except Exception as exc:
            warnings.append(f"{source.source_name()}: {exc}")
    return {
        **state,
        "collected_jobs": jobs,
        "warnings": warnings,
    }


def normalize_jobs_node(state: PipelineState, config: RuntimeConfig) -> PipelineState:
    _ = config
    normalized = []
    seen_urls: set[str] = set()
    for job in state.get("collected_jobs", []):
        url = str(job.url)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        normalized.append(
            job.model_copy(
                update={
                    "title": " ".join(job.title.split()),
                    "company": " ".join(job.company.split()),
                    "location": " ".join(job.location.split()),
                    "normalized_location": job.location.lower(),
                }
            )
        )
    return {**state, "normalized_jobs": normalized}


def rule_filter_jobs_node(state: PipelineState, config: RuntimeConfig) -> PipelineState:
    profile = state["profile"]
    matches = [
        evaluate_rule_match(job, profile, config.recency_days)
        for job in state.get("normalized_jobs", [])
    ]
    filtered_jobs = [
        match.job for match in matches if match.final_score >= config.match_threshold
    ]
    shortlisted = [match for match in matches if match.final_score >= config.match_threshold]
    return {
        **state,
        "filtered_jobs": filtered_jobs,
        "matches": shortlisted,
    }


def llm_rerank_jobs_node(state: PipelineState, config: RuntimeConfig) -> PipelineState:
    if not config.llm.enabled:
        return state

    from app.matching.llm import OptionalLLMReranker

    reranker = OptionalLLMReranker(config.llm)
    matches = reranker.rerank(state.get("matches", []), state["profile"])
    matches = sorted(matches, key=lambda item: item.final_score, reverse=True)
    return {**state, "matches": matches}


def persist_results_node(state: PipelineState, config: RuntimeConfig) -> PipelineState:
    conn = get_connection(config.db_path)
    try:
        init_db(conn)
        repo = JobsRepo(conn)
        new_matches: list[MatchResult] = []
        for match in state.get("matches", []):
            is_new = repo.upsert_match(match)
            if is_new or not config.new_only:
                new_matches.append(match)
    finally:
        conn.close()

    return {
        **state,
        "persisted_count": len(state.get("matches", [])),
        "new_matches": new_matches,
    }


def export_shortlist_node(state: PipelineState, config: RuntimeConfig) -> PipelineState:
    export_path = config.output_dir / "latest_matches.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "title": match.job.title,
            "company": match.job.company,
            "location": match.job.location,
            "source": match.job.source_label,
            "score": match.final_score,
            "decision": match.decision,
            "reason": match.short_reason,
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "url": str(match.job.url),
        }
        for match in state.get("new_matches", [])
    ]
    export_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {**state, "export_path": str(export_path)}


def tailor_cv_for_selected_job_node(
    state: PipelineState, config: RuntimeConfig
) -> PipelineState:
    selected_job_url = state.get("selected_job_url")
    if not selected_job_url:
        return state

    match = next(
        (item for item in state.get("matches", []) if str(item.job.url) == selected_job_url),
        None,
    )
    if match is None:
        warnings = list(state.get("warnings", []))
        warnings.append(f"Selected job not found in shortlisted results: {selected_job_url}")
        return {**state, "warnings": warnings}

    artifact = tailor_cv(state["profile"], match.job)
    write_tailored_artifact(config.output_dir, artifact)
    return {**state, "tailored_artifact": artifact}


def _build_state_graph(config: RuntimeConfig):
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(PipelineState)
    graph.add_node("collect_jobs", lambda state: collect_jobs_node(state, config))
    graph.add_node("normalize_jobs", lambda state: normalize_jobs_node(state, config))
    graph.add_node("rule_filter_jobs", lambda state: rule_filter_jobs_node(state, config))
    graph.add_node("llm_rerank_jobs", lambda state: llm_rerank_jobs_node(state, config))
    graph.add_node("persist_results", lambda state: persist_results_node(state, config))
    graph.add_node("export_shortlist", lambda state: export_shortlist_node(state, config))
    graph.add_node(
        "tailor_cv_for_selected_job",
        lambda state: tailor_cv_for_selected_job_node(state, config),
    )

    graph.add_edge(START, "collect_jobs")
    graph.add_edge("collect_jobs", "normalize_jobs")
    graph.add_edge("normalize_jobs", "rule_filter_jobs")
    graph.add_edge("rule_filter_jobs", "llm_rerank_jobs")
    graph.add_edge("llm_rerank_jobs", "persist_results")
    graph.add_edge("persist_results", "export_shortlist")
    graph.add_edge("export_shortlist", "tailor_cv_for_selected_job")
    graph.add_edge("tailor_cv_for_selected_job", END)
    return graph.compile()


def run_job_discovery_workflow(
    profile: CandidateProfile,
    config: RuntimeConfig,
    selected_job_url: str | None = None,
) -> PipelineState:
    initial_state: PipelineState = {
        "profile": profile,
        "selected_job_url": selected_job_url,
        "warnings": [],
    }

    try:
        graph = _build_state_graph(config)
        return graph.invoke(initial_state)
    except ImportError:
        state = initial_state
        for node in (
            collect_jobs_node,
            normalize_jobs_node,
            rule_filter_jobs_node,
            llm_rerank_jobs_node,
            persist_results_node,
            export_shortlist_node,
            tailor_cv_for_selected_job_node,
        ):
            state = node(state, config)
        return state
