"""SQLite storage layer. Local-first: single file, no cloud."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".ai_job_radar" / "ai_jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases TEXT DEFAULT '[]',
    english_name TEXT,
    website TEXT,
    city TEXT NOT NULL,
    hq_location TEXT,
    company_type TEXT DEFAULT 'startup',
    tracks TEXT DEFAULT '[]',
    description TEXT,
    funding_stage TEXT,
    team_size_min INTEGER,
    team_size_max INTEGER,
    hiring_signals TEXT DEFAULT '[]',
    created_at TEXT,
    updated_at TEXT,
    last_verified_at TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    title TEXT NOT NULL,
    city TEXT NOT NULL,
    location_detail TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_months INTEGER,
    experience TEXT,
    education TEXT,
    jd TEXT,
    source TEXT,
    source_url TEXT,
    source_job_id TEXT,
    posted_at TEXT,
    first_seen_at TEXT,
    last_verified_at TEXT,
    status TEXT DEFAULT 'Recently Seen'
);

CREATE TABLE IF NOT EXISTS funding_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id),
    date TEXT,
    round TEXT,
    amount TEXT,
    currency TEXT,
    investors TEXT DEFAULT '[]',
    note TEXT
);

CREATE TABLE IF NOT EXISTS founders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    title TEXT,
    education TEXT,
    career TEXT,
    relevant_experience TEXT,
    previous_startups TEXT,
    source_fact_kind TEXT DEFAULT 'verified'
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id),
    name TEXT NOT NULL,
    website TEXT,
    positioning TEXT,
    core_features TEXT,
    target_users TEXT,
    scenarios TEXT,
    traction TEXT
);

CREATE TABLE IF NOT EXISTS team_info (
    company_id TEXT PRIMARY KEY REFERENCES companies(id),
    size_min INTEGER,
    size_max INTEGER,
    stage_note TEXT,
    expansion_signals TEXT DEFAULT '[]',
    source_fact_kind TEXT DEFAULT 'verified'
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    source_type TEXT,
    url TEXT,
    publisher TEXT,
    title TEXT,
    snippet TEXT,
    published_at TEXT,
    retrieved_at TEXT,
    trust_note TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT NOT NULL REFERENCES companies(id),
    dimensions TEXT NOT NULL,
    coverage REAL,
    normalized_total REAL,
    computed_at TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS job_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    status TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS company_aliases (
    alias TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id)
);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def jdump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def jload(text: str | None, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default
