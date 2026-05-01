# Agentic Job Discovery and Application Preparation

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

- `AshbySource`
- `GreenhouseSource`
- `LeverSource`
- `PracujSource`
- `NoFluffJobsSource`
- `TheProtocolSource`

Design choices:

- ATS-backed public APIs come first: Ashby, Greenhouse, and Lever use published-job endpoints where possible.
- Broad-market portals come second: Pracuj, No Fluff Jobs, and The Protocol use layered discovery and HTML parsing.
- Network fetchers and HTML/JSON parsers are separated so failures are easier to isolate and test.
- Each source maps into a shared `JobPosting` model.
- Any single source failure is logged and the workflow continues.

### Source Stability Hierarchy

1. ATS-backed public APIs first
2. Broad-market listing parsers second
3. Graceful degradation for brittle or blocked sources

### Why Ashby Was Added

Ashby is increasingly common for startup and AI hiring pipelines, and it exposes a stable public job postings API for published jobs. That makes it a strong interview example of preferring first-party public interfaces over scraping when available.

Example source config:

```json
{
  "type": "ashby",
  "enabled": true,
  "label": "Ashby Boards",
  "config": {
    "job_board_names": ["ashby"],
    "company_name": "Ashby",
    "include_compensation": false
  }
}
```

The implementation uses Ashby’s public job postings API documented at `https://developers.ashbyhq.com/docs/public-job-posting-api`.

### Why Pracuj Uses a Layered Strategy

Pracuj does not offer the same stable, documented public job postings API shape as ATS platforms. To keep the source more robust without browser automation, the adapter uses:

1. sitemap-backed discovery via `robots.txt` and sitemap expansion where possible
2. listing/search page fallback when sitemap discovery is insufficient
3. separate detail fetching for discovered offer URLs
4. graceful degradation with explicit warnings on 403, 429, and 5xx responses

This keeps the scraping strategy explainable and more resilient than relying on one direct search-page request.

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

For Pracuj, you can optionally provide `sitemap_urls` to seed sitemap-backed discovery directly.

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
- Ashby parsing smoke tests
- Pracuj sitemap and listing parser tests
- broad-market parser fixture tests
- SQLite dedup/storage
- rule matcher behavior
- workflow smoke behavior

## Limitations

- Public HTML sources may change markup over time.
- Broad-market HTML parsers are intentionally conservative rather than exhaustive.
- Pracuj sitemap availability and shape may change, so the adapter is designed to fall back rather than fail the workflow.
- CV tailoring is markdown-only in v1.
- LLM reranking assumes a local endpoint such as Ollama and currently uses a simple JSON-oriented prompt flow.

## Roadmap

- richer source-specific detail extraction
- PDF/DOCX export for tailored CV artifacts
- better source-specific pagination and recency handling
- more robust company-name normalization
- explicit human review queues for shortlisted jobs
