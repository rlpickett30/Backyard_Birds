# -*- coding: utf-8 -*-

# birdnet_metadata.py

"""
Created on Fri Nov 28 16:01:39 2025

@author: Lee Pickett

This module creates the minimal “event shell” for the Backyard Acoustic Monitor.

Responsibilities:
- Generate a unique event_id for every detection event.
- Attach the node_id that identifies this physical station (for example, "yard_station_1").
- Stamp each event with both UTC and local timestamps using the configured time zone.
- Reserve a weather field (currently None) that can be populated later by a weather module.

Debugging notes:
- This module uses the standard logging library. By default it is silent.
- When run directly (`python birdnet_metadata.py`), it will configure logging at DEBUG
  level and print a sample event shell to the console.
- When imported from other modules, the logger inherits whatever configuration the
  main application sets.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
import socket
import uuid

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.metadata")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# You can change these later or load them from a config file.
NODE_ID = "yard_station_1"
LOCAL_TZ = ZoneInfo("America/Denver")


@dataclass(frozen=True)
class EventShell:
    """Minimal, BirdNET-agnostic event metadata."""
    event_id: str
    node_id: str
    timestamp_utc: str
    local_time: str
    weather: dict | None = None  # placeholder for future weather block

    def to_dict(self) -> dict:
        return asdict(self)


def _now_utc() -> datetime:
    ts = datetime.now(timezone.utc)
    logger.debug("Generated UTC timestamp: %s", ts.isoformat(timespec="milliseconds"))
    return ts


def _make_event_id(ts: datetime) -> str:
    """Build a unique, sortable event ID from timestamp + short random suffix."""
    ts_part = ts.strftime("%Y%m%dT%H%M%S.%fZ")
    rand_part = uuid.uuid4().hex[:8]
    event_id = f"{ts_part}_{rand_part}"
    logger.debug("Constructed event_id: %s (ts_part=%s, rand=%s)", event_id, ts_part, rand_part)
    return event_id


def new_event_shell(node_id: str | None = None) -> EventShell:
    """
    Create a fresh EventShell with:
      - event_id
      - node_id
      - UTC and local timestamps
      - weather=None (to be filled by weather module later)
    """
    effective_node_id = node_id or NODE_ID

    ts_utc = _now_utc()
    ts_local = ts_utc.astimezone(LOCAL_TZ)
    event_id = _make_event_id(ts_utc)

    logger.debug(
        "Creating new EventShell: node_id=%s, event_id=%s, utc=%s, local=%s, host=%s",
        effective_node_id,
        event_id,
        ts_utc.isoformat(timespec="milliseconds"),
        ts_local.isoformat(timespec="milliseconds"),
        socket.gethostname(),
    )

    shell = EventShell(
        event_id=event_id,
        node_id=effective_node_id,
        timestamp_utc=ts_utc.isoformat(timespec="milliseconds"),
        local_time=ts_local.isoformat(timespec="milliseconds"),
        weather=None,
    )

    logger.debug("EventShell created: %s", shell.to_dict())
    return shell


if __name__ == "__main__":
    # Standalone debug run: print one sample event shell.
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Running birdnet_metadata.py as a script for debug/demo.")
    sample = new_event_shell()
    print("Sample EventShell as dict:")
    print(sample.to_dict())
