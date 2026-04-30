from __future__ import annotations

import sqlite3
from pathlib import Path


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Create a SQLite connection and ensure the parent directory exists."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize database schema on first run."""

    conn.execute("PRAGMA foreign_keys = ON;")

    # Create base schema. For evolving fields we also apply lightweight
    # `ALTER TABLE` migrations below (safe for this tiny v0 POC).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            url TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            level TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT,
            commitment TEXT,
            source_job_id TEXT,
            posted_at TEXT,
            match_score INTEGER NOT NULL,
            match_reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )

    ensure_cols = {
        "category": "TEXT",
        "commitment": "TEXT",
        "source_job_id": "TEXT",
        "posted_at": "TEXT",
    }
    cur = conn.execute("PRAGMA table_info(jobs);")
    existing_cols = {row["name"] for row in cur.fetchall()}
    for col, typ in ensure_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {typ};")

    conn.commit()

