# Job Agent (v0) - rule-based job monitor POC

Minimal local CLI that:
1. Fetches job postings from adapters (`DummySource` and optionally Greenhouse / Lever)
2. Scores them with rule-based matching against a candidate profile
3. Stores seen job URLs in SQLite
4. Prints **only new matching jobs** on each run

## Run

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Configuration

By default the SQLite DB is created at `./jobs.sqlite`.

Candidate profile is loaded from `./candidate_profile.json` at runtime.

Required JSON fields:

- `target_levels`
- `target_locations`
- `target_domains`
- `include_keywords`
- `exclude_keywords`

Optional environment variables:

- `JOB_AGENT_DB_PATH` - path to the SQLite database file
- `JOB_AGENT_MATCH_THRESHOLD` - integer match score threshold (default: `60`)

### Greenhouse (optional)

The Greenhouse Job Board API uses a `board_token`, which is the token part of a board URL, e.g.:

- `https://boards.greenhouse.io/<board_token>`

To enable Greenhouse fetching, set:

- `JOB_AGENT_GREENHOUSE_ENABLED=true`
- `JOB_AGENT_GREENHOUSE_BOARD_TOKENS` - comma-separated list of one or more `board_token` values

Example:

```bash
export JOB_AGENT_GREENHOUSE_ENABLED=true
export JOB_AGENT_GREENHOUSE_BOARD_TOKENS=acme,acme-emea
python -m app.main
```

If a token is invalid/unreachable, the CLI prints a readable warning and continues with other sources.

### Lever (optional)

Lever's public postings access is namespaced by a *site/company handle*.
That handle is the part of the Lever URL after `jobs.lever.co/`, for example:

- `https://jobs.lever.co/acme` → handle: `acme`

To enable Lever fetching, set:

- `JOB_AGENT_LEVER_ENABLED=true`
- `JOB_AGENT_LEVER_HANDLES` - comma-separated list of one or more `jobs.lever.co/<handle>` values

Example:

```bash
export JOB_AGENT_LEVER_ENABLED=true
export JOB_AGENT_LEVER_HANDLES=acme,acme-eu
python -m app.main
```

If a handle is invalid/unreachable, the CLI prints a readable warning and continues with other sources.

## Export

After each run, the CLI writes the **new** matching jobs from this run to:

`./output/latest_matches.json`

The `output/` directory is created automatically if it does not exist.

## What to expect

On the first run, the CLI should print new matching dummy postings.
On subsequent runs, it prints nothing until a new URL appears in the source.

