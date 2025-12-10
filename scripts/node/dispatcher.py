# dispatcher.py

from __future__ import annotations

from typing import Any, Dict
import logging
import os

from birdnet_manager import run_live_loop
from send_over_wifi import send_event
from node_database import NodeDatabase

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.dispatcher")

# ---------------------------------------------------------------------------
# Node database configuration
# ---------------------------------------------------------------------------

# You can change this to an absolute path if you prefer.
# For now, store the SQLite file next to this script.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "node_events.db")

node_db = NodeDatabase(DB_PATH)

# ---------------------------------------------------------------------------
# Core dispatcher API
# ---------------------------------------------------------------------------


def _flush_pending_events() -> None:
    """
    Try to flush any previously queued events over Wi-Fi.

    This is called opportunistically each time a new event arrives.
    If the network is still down, flush_pending() will abort on the
    first failure and we will try again on the next event.
    """
    try:
        if node_db.has_pending():
            logger.info("Pending queued events detected; attempting flush.")
            node_db.flush_pending(send_event)
            if not node_db.has_pending():
                logger.info("All queued events have been flushed successfully.")
            else:
                logger.info("Some queued events remain; will retry later.")
    except Exception as exc:
        # Defensive: do not crash the node because flushing failed.
        logger.exception("Error while flushing queued events: %s", exc)


def handle_event(event: Dict[str, Any]) -> None:
    """
    Entry point used by birdnet_manager to deliver completed events.

    Args:
        event:
            A JSON-serializable event dictionary. It is assumed to already
            contain an event_id, node_id, timestamps, and bird/model fields
            as constructed by birdnet_manager + birdnet_metadata.
    """
    event_id = event.get("event_id", "<no-event-id>")
    logger.info("Dispatcher received event_id=%s", event_id)
    logger.debug("Full event payload: %s", event)

    # First, opportunistically try to flush any previously queued events.
    _flush_pending_events()

    # Now try to send this event over Wi-Fi.
    try:
        send_event(event)
        logger.info("Event dispatched over Wi-Fi for event_id=%s", event_id)
    except Exception as exc:  # pragma: no cover – defensive guardrail
        logger.exception(
            "Failed to send event over Wi-Fi for event_id=%s, queuing locally: %s",
            event_id,
            exc,
        )
        # Queue the event so it will be retried on a future flush.
        try:
            node_db.queue_event(event)
            logger.info("Event queued locally in node database: event_id=%s", event_id)
        except Exception as db_exc:
            # This is the worst-case scenario: network down and DB write failed.
            logger.exception(
                "Failed to queue event in local database; event may be lost. "
                "event_id=%s, db_error=%s",
                event_id,
                db_exc,
            )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Node main loop.

    This function wires the BirdNET manager pipeline into the dispatcher by
    passing handle_event() as the callback to birdnet_manager.run_live_loop().

    The manager is responsible for:
    - Recording audio via microphone_loop.
    - Running BirdNET analysis via birdnet_analyzer.
    - Building complete event dictionaries via birdnet_metadata.
    - Invoking handle_event() for each event it decides to emit.
    """
    logger.info("Starting dispatcher main loop in BirdNET manager mode.")
    logger.info(
        "All events from birdnet_manager will be sent over Wi-Fi via "
        "send_over_wifi, with local queueing fallback."
    )
    logger.info("Node database path: %s", DB_PATH)

    # Under normal operation this does not return; Ctrl+C to stop.
    run_live_loop(handle_event)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
