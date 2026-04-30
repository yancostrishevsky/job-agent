# Agentic Job Discovery and Application Preparation

Professional, interview-ready Python project for discovering AI/ML internships and junior roles in Poland, scoring them with deterministic rules plus optional LLM reranking, persisting results in SQLite, and preparing guarded CV artifacts for selected postings.

## Problem Statement

Searching for junior AI/ML roles across multiple job boards is repetitive and noisy. Different sources expose different schemas, seniority labels, and location conventions. This project demonstrates how to build an agentic but controlled pipeline that:

- collects jobs from multiple sources
- normalizes them into a shared schema
- filters and scores them deterministically
- optionally reranks them semantically with an LLM
- persists and exports shortlisted results
- prepares tailored CV materials without inventing experience

## Why This Is Agentic

The system uses a stateful workflow with explicit nodes, shared state, branching-friendly boundaries, and recoverable steps. Each node performs a bounded responsibility while passing structured state forward.

LangGraph is the primary orchestration layer because it makes the pipeline easy to explain:

- collection is isolated from normalization
- deterministic filtering happens before LLM use
- persistence and export are explicit side-effect nodes
- CV tailoring is a separate terminal action, not mixed into discovery

## Architecture

```text
CandidateProfile + sources.json
        |
        v
collect_jobs --> normalize_jobs --> rule_filter_jobs --> llm_rerank_jobs
                                                           |
                                                           v
tailor_cv_for_selected_job <-- export_shortlist <-- persist_results
```

### Package Layout

```text
app/
  config/
  cv/
  matching/
  models/
  sources/
  storage/
  workflows/
  db.py
  main.py
tests/
output/
candidate_profile.json
sources.json
AGENTS.md
.codex/config.toml
```

## Source Strategy

V1 includes:

- `GreenhouseSource`
- `LeverSource`
- `PracujSource`
- `NoFluffJobsSource`
- `TheProtocolSource`

Design choices:

- Greenhouse and Lever use public published-job endpoints where possible.
- Pracuj, No Fluff Jobs, and The Protocol use broad-market discovery pages and HTML parsing.
- Network fetchers and HTML/JSON parsers are separated so failures are easier to isolate and test.
- Each source maps into a shared `JobPosting` model.
- Any single source failure is logged and the workflow continues.

## Matching Strategy

### 1. Deterministic First

The rule engine prioritizes explainability and predictable fallback behavior:

- targets internship, junior, graduate, trainee, and entry-level roles
- boosts Krakow, Kraków, Poland, remote, and hybrid-friendly locations
- boosts AI / ML / NLP / CV / research / MLOps-adjacent signals
- penalizes senior, lead, principal, staff, and manager signals
- supports optional recency scoring

Each shortlisted result carries human-readable reasons, matched skills, missing skills, and a decision.

### 2. Optional LLM Reranking

Only jobs that pass the rule stage are eligible for reranking. The LLM is expected to return structured JSON with:

- `fit_score`
- `decision`
- `matched_skills`
- `missing_skills`
- `seniority_fit`
- `location_fit`
- `short_reason`

If the LLM is disabled or unavailable, the workflow returns deterministic results only.

## CV Tailoring Guardrails

The tailoring step accepts a master candidate profile and one selected job posting, then writes:

- `output/tailored_cv.md`
- `output/tailored_cover_note.md`

Guardrails:

- never invent experience
- never invent employers
- never inflate years of experience
- never add fake projects
- only reorder, condense, or emphasize verified profile content

## Configuration

### `candidate_profile.json`

Holds the candidate preferences plus verified CV material such as skills, projects, work experience, and education.

### `sources.json`

Defines enabled sources and source-specific configuration, for example board tokens, Lever handles, or discovery URLs.

### Environment Variables

- `JOB_AGENT_DB_PATH`
- `JOB_AGENT_OUTPUT_DIR`
- `JOB_AGENT_CANDIDATE_PROFILE`
- `JOB_AGENT_SOURCES_CONFIG`
- `JOB_AGENT_MATCH_THRESHOLD`
- `JOB_AGENT_RECENCY_DAYS`
- `JOB_AGENT_NEW_ONLY`
- `JOB_AGENT_LLM_ENABLED`
- `JOB_AGENT_LLM_PROVIDER`
- `JOB_AGENT_LLM_MODEL`
- `JOB_AGENT_LLM_BASE_URL`
- `JOB_AGENT_LLM_TIMEOUT_SECONDS`
- `JOB_AGENT_SELECTED_JOB_URL`

## Run

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

The CLI prints enabled sources and summary counts, persists jobs to SQLite, and writes `output/latest_matches.json`.

## Sample Output

```json
[
  {
    "title": "Junior ML Engineer",
    "company": "Acme",
    "location": "Krakow, Poland",
    "source": "Pracuj AI/ML Search",
    "score": 84,
    "decision": "strong_match",
    "reason": "seniority=target_level; location=target_location; domains=machine learning",
    "matched_skills": ["Python", "PyTorch"],
    "missing_skills": ["TensorFlow"],
    "url": "https://example.com/job"
  }
]
```

## Tests

```bash
python3 -m pytest
```

Current lightweight coverage includes:

- model validation
- source parser smoke tests
- SQLite dedup/storage
- rule matcher behavior
- workflow smoke behavior

## Limitations

- Public HTML sources may change markup over time.
- Broad-market HTML parsers are intentionally conservative rather than exhaustive.
- CV tailoring is markdown-only in v1.
- LLM reranking assumes a local endpoint such as Ollama and currently uses a simple JSON-oriented prompt flow.

## Roadmap

- richer source-specific detail extraction
- PDF/DOCX export for tailored CV artifacts
- better source-specific pagination and recency handling
- more robust company-name normalization
- explicit human review queues for shortlisted jobs
