# -*- coding: utf-8 -*-

"""
database.py

SQLite storage for Backyard Bird Station events.

Databases:
    - db/working.db : raw detections (table: detections)
    - db/yearly.db  : yearly rollups (table: yearly_summary)

Typical usage from server_dispatcher.py:

    from database import insert_event, init_db

    def handle_event(event, sender):
        insert_event(event)

    if __name__ == "__main__":
        init_db()
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from create_database import (
    WORKING_DB_PATH,
    YEARLY_DB_PATH,
    WORKING_SCHEMA,
    YEARLY_SCHEMA,
    init_database,
    ensure_db_dir,
)

logger = logging.getLogger("birdstation.database")

# ---------------------------------------------------------------------------
# Internal helpers: singleton connections
# ---------------------------------------------------------------------------

_working_conn: Optional[sqlite3.Connection] = None
_yearly_conn: Optional[sqlite3.Connection] = None


def _get_working_connection() -> sqlite3.Connection:
    """Return a singleton SQLite connection to db/working.db, creating it if needed."""
    global _working_conn
    if _working_conn is None:
        ensure_db_dir()
        init_database(WORKING_DB_PATH, WORKING_SCHEMA)

        logger.info("Opening SQLite database at %s", WORKING_DB_PATH)
        _working_conn = sqlite3.connect(WORKING_DB_PATH)
        _working_conn.row_factory = sqlite3.Row
    return _working_conn


def _get_yearly_connection() -> sqlite3.Connection:
    """Return a singleton SQLite connection to db/yearly.db, creating it if needed."""
    global _yearly_conn
    if _yearly_conn is None:
        ensure_db_dir()
        init_database(YEARLY_DB_PATH, YEARLY_SCHEMA)

        logger.info("Opening yearly SQLite database at %s", YEARLY_DB_PATH)
        _yearly_conn = sqlite3.connect(YEARLY_DB_PATH)
        _yearly_conn.row_factory = sqlite3.Row
    return _yearly_conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Optional explicit initializer.

    You normally do not need to call this; the first insert_event() will
    open the databases and ensure the schemas. It is convenient for
    standalone inspection via `python database.py`.
    """
    _ = _get_working_connection()
    _ = _get_yearly_connection()


def _parse_year_from_timestamp(ts: Optional[str]) -> Optional[int]:
    """Extract the four-digit year from an ISO timestamp string."""
    if not ts or len(ts) < 4:
        return None
    try:
        return int(ts[:4])
    except ValueError:
        return None


def _update_yearly_summary(detection_row: Dict[str, Any]) -> None:
    """
    Update yearly_summary in yearly.db for the given detection.

    detection_row keys (from insert_event):
        detected_at_utc, species_code, common_name, confidence
    """
    ts = detection_row.get("detected_at_utc")
    species_code = detection_row.get("species_code")
    common_name = detection_row.get("common_name")
    confidence = detection_row.get("confidence")

    year = _parse_year_from_timestamp(ts)
    if year is None or not species_code or not common_name:
        # If we cannot determine year or species, skip the rollup.
        logger.debug(
            "Skipping yearly_summary update (year/species missing): ts=%r species=%r",
            ts,
            species_code,
        )
        return

    conn = _get_yearly_connection()
    cur = conn.cursor()

    # Fetch existing row for (year, species_code), if any.
    cur.execute(
        """
        SELECT
            id,
            total_detections,
            first_seen_utc,
            last_seen_utc,
            max_confidence
        FROM yearly_summary
        WHERE year = ? AND species_code = ?;
        """,
        (year, species_code),
    )
    existing = cur.fetchone()

    if existing is None:
        # New species-year combination.
        cur.execute(
            """
            INSERT INTO yearly_summary (
                year,
                species_code,
                common_name,
                total_detections,
                first_seen_utc,
                last_seen_utc,
                max_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                year,
                species_code,
                common_name,
                1,
                ts,
                ts,
                confidence if confidence is not None else 0.0,
            ),
        )
        logger.debug(
            "Inserted new yearly_summary row: year=%s species=%s",
            year,
            species_code,
        )
    else:
        # Update existing row.
        total = (existing["total_detections"] or 0) + 1
        first_seen = existing["first_seen_utc"] or ts
        last_seen = existing["last_seen_utc"] or ts

        # Compare timestamps lexicographically; ISO 8601 ordering makes this safe.
        if ts is not None:
            if first_seen is None or ts < first_seen:
                first_seen = ts
            if last_seen is None or ts > last_seen:
                last_seen = ts

        # Confidence.
        old_max = existing["max_confidence"] or 0.0
        new_max = old_max
        if confidence is not None and confidence > old_max:
            new_max = confidence

        cur.execute(
            """
            UPDATE yearly_summary
            SET
                total_detections = ?,
                first_seen_utc = ?,
                last_seen_utc = ?,
                max_confidence = ?
            WHERE id = ?;
            """,
            (total, first_seen, last_seen, new_max, existing["id"]),
        )
        logger.debug(
            "Updated yearly_summary row: year=%s species=%s total=%s",
            year,
            species_code,
            total,
        )

    conn.commit()


def insert_event(event: Dict[str, Any]) -> None:
    """
    Insert a single event dictionary into the working detections table,
    and update the yearly rollup in yearly.db.

    Expected event structure (loosely):

        {
            "event_id": "...",
            "node_id": "yard_station_1",
            "timestamp_utc": "2025-12-06T23:17:52.458+00:00",
            "event_type": "birdnet_detection",
            "bird": {
                "species_code": "blbill",
                "common_name": "Black-billed Magpie",
                "scientific_name": "...",
                "confidence": 0.73,
                ...
            },
            ...
        }
    """

    conn = _get_working_connection()
    cur = conn.cursor()

    bird = event.get("bird") or {}
    audio = event.get("audio") or {}
    model = event.get("model") or {}

    detected_at_utc = event.get("timestamp_utc") or event.get("detected_at_utc")

    detection_row = {
        "detected_at_utc": detected_at_utc,
        "species_code": bird.get("species_code"),
        "common_name": bird.get("common_name"),
        "scientific_name": bird.get("scientific_name"),
        "confidence": bird.get("confidence"),

        "latitude": (
            event.get("lat")
            or event.get("latitude")
            or model.get("lat")
        ),
        "longitude": (
            event.get("lon")
            or event.get("longitude")
            or model.get("lon")
        ),

        "node_id": event.get("node_id"),
        "audio_path": audio.get("file"),

        "is_rare": 0,
        "review_status": "unreviewed",
        "notes": None,
    }

    logger.info(
        "Inserting detection into working.db: event_id=%s species=%s conf=%s",
        event.get("event_id"),
        detection_row["species_code"],
        (
            f"{detection_row['confidence']:.3f}"
            if detection_row["confidence"] is not None
            else "None"
        ),
    )

    # Insert into working.detections
    cur.execute(
        """
        INSERT INTO detections (
            detected_at_utc,
            species_code,
            common_name,
            scientific_name,
            confidence,
            latitude,
            longitude,
            node_id,
            audio_path,
            is_rare,
            review_status,
            notes
        ) VALUES (
            :detected_at_utc,
            :species_code,
            :common_name,
            :scientific_name,
            :confidence,
            :latitude,
            :longitude,
            :node_id,
            :audio_path,
            :is_rare,
            :review_status,
            :notes
        );
        """,
        detection_row,
    )

    conn.commit()

    # Update yearly rollup.
    _update_yearly_summary(detection_row)


# ---------------------------------------------------------------------------
# Simple CLI / debug helper
# ---------------------------------------------------------------------------

def list_recent(limit: int = 10) -> None:
    """
    Print the most recent N detections for quick inspection.

    You can run `python database.py` on your PC to see what is being stored
    in db/working.db.
    """
    conn = _get_working_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            detected_at_utc,
            node_id,
            species_code,
            common_name,
            confidence
        FROM detections
        ORDER BY detected_at_utc DESC
        LIMIT ?;
        """,
        (limit,),
    )
    rows = cur.fetchall()
    print(f"Most recent {len(rows)} detections:")
    for r in rows:
        print(
            f"{r['detected_at_utc']}  "
            f"{(r['node_id'] or ''):>12}  "
            f"{(r['species_code'] or '????'):>8}  "
            f"{(r['confidence'] or 0):5.3f}  "
            f"{r['common_name']}"
        )


def list_yearly(year: Optional[int] = None) -> None:
    """
    Print yearly_summary rows, optionally filtered by year.

    Example:
        python database.py      # show all
        python database.py 2025 # show only 2025
    """
    conn = _get_yearly_connection()
    cur = conn.cursor()

    if year is None:
        cur.execute(
            """
            SELECT
                year,
                species_code,
                common_name,
                total_detections,
                first_seen_utc,
                last_seen_utc,
                max_confidence
            FROM yearly_summary
            ORDER BY year, species_code;
            """
        )
    else:
        cur.execute(
            """
            SELECT
                year,
                species_code,
                common_name,
                total_detections,
                first_seen_utc,
                last_seen_utc,
                max_confidence
            FROM yearly_summary
            WHERE year = ?
            ORDER BY species_code;
            """,
            (year,),
        )

    rows = cur.fetchall()
    print(f"Yearly summary rows: {len(rows)}")
    for r in rows:
        print(
            f"{r['year']}  {r['species_code']:>8}  "
            f"{r['total_detections']:4d}  "
            f"{r['max_confidence'] or 0:5.3f}  "
            f"{r['common_name']}  "
            f"[{r['first_seen_utc']} → {r['last_seen_utc']}]"
        )


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    init_db()

    if len(sys.argv) == 1:
        list_recent(20)
        print()
        list_yearly()
    else:
        try:
            year_arg = int(sys.argv[1])
        except ValueError:
            year_arg = None
        list_yearly(year_arg)
