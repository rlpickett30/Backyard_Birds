#!/usr/bin/env python3
"""
create_databases.py

Create three SQLite databases for the Birding Monitor Station:

1. working.db  - Raw detection log (every detection).
2. yearly.db   - Yearly rollups per species.
3. rarity.db   - Rarity definitions per species / region.

All databases are stored in a local "db" directory next to this script.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Directory that will hold all database files
BASE_DIR = Path(__file__).resolve().parent
DB_DIR = BASE_DIR / "db"

WORKING_DB_PATH = DB_DIR / "working.db"
YEARLY_DB_PATH = DB_DIR / "yearly.db"
RARITY_DB_PATH = DB_DIR / "rarity.db"


def ensure_db_dir() -> None:
    """Ensure the database directory exists."""
    DB_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Working Database (raw detections) ----------

WORKING_SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at_utc TEXT NOT NULL,           -- ISO timestamp, e.g. '2025-12-06T15:23:01Z'
    year INTEGER GENERATED ALWAYS AS (
        CAST(substr(detected_at_utc, 1, 4) AS INTEGER)
    ) VIRTUAL,                               -- Convenience year field (SQLite 3.31+)
    species_code TEXT NOT NULL,              -- Short code (e.g. 'baleag' for Bald Eagle)
    common_name TEXT NOT NULL,               -- Human-readable bird name
    scientific_name TEXT,                    -- Optional scientific name
    confidence REAL NOT NULL,                -- 0.0–1.0 BirdNET confidence
    latitude REAL,                           -- Optional location fields
    longitude REAL,
    node_id TEXT,                            -- Which station / node produced this record
    audio_path TEXT,                         -- Path to associated audio clip, if kept
    is_rare INTEGER DEFAULT 0,               -- 0 = normal, 1 = flagged as rare
    review_status TEXT DEFAULT 'unreviewed', -- 'unreviewed' | 'accepted' | 'rejected'
    notes TEXT                               -- Free-form notes or curator comments
);

CREATE INDEX IF NOT EXISTS idx_detections_time
    ON detections (detected_at_utc);

CREATE INDEX IF NOT EXISTS idx_detections_species_time
    ON detections (species_code, detected_at_utc);

CREATE INDEX IF NOT EXISTS idx_detections_is_rare
    ON detections (is_rare);
"""


# ---------- Yearly Database (summary per year / species) ----------

YEARLY_SCHEMA = """
CREATE TABLE IF NOT EXISTS yearly_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    species_code TEXT NOT NULL,
    common_name TEXT NOT NULL,
    total_detections INTEGER NOT NULL DEFAULT 0,
    first_seen_utc TEXT,   -- First detection timestamp in that year
    last_seen_utc TEXT,    -- Most recent detection timestamp in that year
    max_confidence REAL,   -- Highest confidence recorded in that year
    UNIQUE (year, species_code)
);

CREATE INDEX IF NOT EXISTS idx_yearly_year
    ON yearly_summary (year);

CREATE INDEX IF NOT EXISTS idx_yearly_species
    ON yearly_summary (species_code);
"""


# ---------- Rarity Database (rarity rules / configuration) ----------

RARITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS rarity_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_code TEXT NOT NULL,     -- e.g. 'SW_CO', 'CO-LA_PLATEAU'
    species_code TEXT NOT NULL,    -- Matches working/yearly species_code
    common_name TEXT NOT NULL,
    rarity_level TEXT NOT NULL,    -- e.g. 'common', 'uncommon', 'rare', 'vagrant'
    max_expected_per_year INTEGER, -- Optional threshold (e.g. > 5 = suspicious)
    notes TEXT,
    UNIQUE (region_code, species_code)
);

CREATE INDEX IF NOT EXISTS idx_rarity_region
    ON rarity_rules (region_code);

CREATE INDEX IF NOT EXISTS idx_rarity_species
    ON rarity_rules (species_code);
"""


def init_database(path: Path, schema_sql: str) -> None:
    """
    Create a SQLite database at `path` (if it does not exist) and
    apply the given schema.
    """
    print(f"[db] Initializing {path.name} ...")
    conn = sqlite3.connect(path)
    try:
        with conn:
            conn.executescript(schema_sql)
    finally:
        conn.close()
    print(f"[db] {path.name} ready.")


def main() -> None:
    ensure_db_dir()

    # Create each database with its schema
    init_database(WORKING_DB_PATH, WORKING_SCHEMA)
    init_database(YEARLY_DB_PATH, YEARLY_SCHEMA)
    init_database(RARITY_DB_PATH, RARITY_SCHEMA)

    print("\n[db] All databases initialized in:", DB_DIR)


if __name__ == "__main__":
    main()
