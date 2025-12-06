# -*- coding: utf-8 -*-

# dispatcher.py

"""
Backyard_Birds node – central dispatcher (BirdNET v2 pipeline).

This module is the “traffic controller” for the Backyard Acoustic Monitor node.
It sits between:

    birdnet_manager.run_live_loop()  →  dispatcher.handle_event()  →  send_over_wifi.send_event()

Responsibilities in this version:
- Start the BirdNET manager live loop.
- Receive fully-formed event dictionaries from the manager.
- Forward those events to send_over_wifi for UDP transmission.
- Provide logging around event flow and lifecycle.

The lower layers (microphone_loop, birdnet_analyzer, birdnet_metadata, send_over_wifi)
do not import this module; dependencies are one-way.
"""

from __future__ import annotations

from typing import Any, Dict
import logging

from birdnet_manager import run_live_loop
from send_over_wifi import send_event

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.dispatcher")

# ---------------------------------------------------------------------------
# Core dispatcher API
# ---------------------------------------------------------------------------


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

    # Fire-and-forget send over Wi-Fi. Failures are logged but do not crash
    # the main loop; this node is intended to run for days at a time.
    try:
        send_event(event)
        logger.info("Event dispatched over Wi-Fi for event_id=%s", event_id)
    except Exception as exc:  # pragma: no cover – defensive guardrail
        logger.exception(
            "Failed to send event over Wi-Fi for event_id=%s: %s",
            event_id,
            exc,
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
        "All events from birdnet_manager will be sent over Wi-Fi via send_over_wifi."
    )

    # Under normal operation this does not return; Ctrl+C to stop.
    run_live_loop(handle_event)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()

