# Repository Guidance

## Purpose
Build an interview-ready agentic job discovery and CV tailoring system for AI/ML internships and junior roles in Poland, with Krakow and remote-friendly roles as the primary focus.

## Engineering Style
- Keep the code modular, typed, and easy to narrate in an interview.
- Prefer explicit orchestration boundaries over implicit helper chains.
- Use deterministic logic first; treat LLM behavior as optional enhancement, never a hard dependency.
- Preserve graceful degradation for flaky or unavailable job sources.

## Architecture Conventions
- `app/models/` holds shared pydantic domain models and workflow state.
- `app/sources/` separates fetchers from parsers and maps every source into `JobPosting`.
- `app/matching/` contains deterministic scoring and optional LLM reranking.
- `app/storage/` owns SQLite persistence and deduplication behavior.
- `app/workflows/` owns LangGraph orchestration nodes and graph assembly.
- `app/cv/` owns CV tailoring and output artifacts with strict non-invention guardrails.

## Source Adapter Rules
- Keep network access and parsing in separate classes.
- Fail one source at a time, never fail the whole pipeline because a single source changed.
- Prefer stable public endpoints when available before HTML scraping.
- Use broad, resilient selectors for HTML parsers and cover them with parser smoke tests.

## Matching Rules
- Deterministic filtering runs before any LLM call.
- Penalize senior/staff/lead/manager roles aggressively.
- Keep explainability first-class: every shortlisted result should have readable reasons.
- If the LLM is unavailable, return rule-based results without breaking the run.

## CV Guardrails
- Never invent employers, projects, degrees, or years of experience.
- Tailoring may reorder and emphasize only verified profile content.
- Future project suggestions belong outside the tailored CV artifact.

## Testing
- Keep tests lightweight and local.
- Prefer parser smoke tests with embedded fixture strings over live network tests.
- Maintain at least coverage for models, storage/dedup, rules, and workflow smoke behavior.
