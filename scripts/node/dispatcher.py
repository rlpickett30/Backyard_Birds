# -*- coding: utf-8 -*-

# dispatcher.py

"""
Backyard_Birds node – central dispatcher.

This module is the “traffic controller” for the Backyard Acoustic Monitor
node. It sits between the raw detection pipeline (microphone + BirdNET) and
all outbound communication paths (currently UDP over Wi-Fi).

Responsibilities in Version 1:
- Accept a single BirdNET detection triple: (bird_id, species_name, confidence).
- Wrap that triple in a BirdDetection object.
- Ask birdnet_lite_manager.build_event_from_detection() to construct a full,
  standardized event dictionary that includes node metadata and timestamps.
- Forward that event to send_over_wifi.send_event() for UDP transmission to
  a listening PC or gateway.
- Provide a main loop that runs the live microphone capture via
  microphone_loop.run_live_loop(), using dispatch_detection() as the callback.

Future versions:
- Accept batched detections from a single audio window.
- Route events to multiple sinks (UDP, local JSON log, database, message bus).
- Implement basic queueing or retry behavior when Wi-Fi is down.
- Integrate health checks and watchdog signalling.

If you come back to this project months from now and wonder:
“Where does a raw BirdNET detection become a standard event and actually leave
the node?”, this module is the answer.
"""

from __future__ import annotations

from typing import Any, Dict
import logging

from birdnet_lite_manager import BirdDetection, build_event_from_detection
from send_over_wifi import send_event
from microphone_loop import run_live_loop

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.dispatcher")

# ---------------------------------------------------------------------------
# Core dispatcher API
# ---------------------------------------------------------------------------


def dispatch_detection(
    bird_id: str,
    species_name: str,
    confidence: float,
) -> Dict[str, Any]:
    """
    High-level entry point for the node pipeline.

    This function is called whenever the inner pipeline (microphone +
    BirdNET Analyzer) produces a detection. It builds a BirdDetection,
    converts it into a complete event using the manager, and then forwards
    that event over Wi-Fi.

    Args:
        bird_id:
            Short ID or code for the species (for example, "AMRO").
        species_name:
            Human-readable common name (for example, "American Robin").
        confidence:
            Model confidence in [0.0, 1.0].

    Returns:
        The full event dictionary that was sent. This is useful for testing
        or for any upstream code that wants to inspect or log the event
        after dispatch.
    """
    logger.debug(
        "dispatch_detection() called with bird_id=%s, species_name=%s, confidence=%s",
        bird_id,
        species_name,
        confidence,
    )

    detection = BirdDetection(
        bird_id=bird_id,
        species_name=species_name,
        confidence=confidence,
    )
    logger.debug("Constructed BirdDetection: %s", detection.to_dict())

    event = build_event_from_detection(detection)
    logger.info(
        "Event built for species=%s (id=%s, conf=%.3f) with event_id=%s",
        species_name,
        bird_id,
        confidence,
        event.get("event_id"),
    )

    # Fire-and-forget send over Wi-Fi. Failures are logged but do not crash
    # the main loop; this node is intended to run for days at a time.
    try:
        send_event(event)
        logger.info(
            "Event dispatched over Wi-Fi for event_id=%s",
            event.get("event_id"),
        )
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.exception(
            "Failed to send event over Wi-Fi for event_id=%s: %s",
            event.get("event_id"),
            exc,
        )

    logger.debug(
        "dispatch_detection() completed for event_id=%s",
        event.get("event_id"),
    )
    return event


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Node main loop.

    This function wires the live microphone capture pipeline into the
    dispatcher by passing dispatch_detection() as the callback to
    microphone_loop.run_live_loop().

    The microphone loop is responsible for:
    - Recording short audio chunks from the USB microphone.
    - Calling BirdNET Analyzer on each chunk.
    - Invoking dispatch_detection() for every detection it finds.
    """
    logger.info("Starting dispatcher main loop in live microphone mode.")
    logger.info(
        "All detections from the microphone pipeline will be wrapped into "
        "events and sent over Wi-Fi."
    )

    # run_live_loop() will not return under normal operation; it records,
    # analyzes, and calls dispatch_detection() in a long-running loop.
    # The arecord device is configured inside microphone_loop; update there
    # if you change hardware.
    run_live_loop(dispatch_detection)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
