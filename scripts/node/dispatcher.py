# -*- coding: utf-8 -*-

# dispatcher.py

"""
Created on Fri Nov 28 19:15:00 2025

@author: Lee Pickett

This module is the central “traffic controller” for the Backyard Acoustic
Monitor node. It receives raw BirdNET detections from the inner pipeline,
asks birdnet_lite_manager.py to build a full event object (metadata + model
info + detection), and then sends that event over Wi-Fi using send_over_wifi.py.

Version 1 responsibilities:
- Accept a single detection (bird_id, species_name, confidence) from upstream
  code (e.g., the BirdNET Analyzer adapter or watchdog layer).
- Use birdnet_lite_manager.BirdDetection + build_event_from_detection() to
  construct a complete event dictionary.
- Forward that event to send_over_wifi.send_event() for transmission to a
  listening PC or gateway.
- Log the flow for debugging and traceability.

Future versions (Version 2+):
- Accept batched detections (e.g., multiple species within one 3-second window).
- Route events to multiple sinks (local file logger, database, message queue,
  in addition to send_over_wifi).
- Implement simple backpressure or queueing if downstream links are slow.
- Integrate with a watchdog or supervisor process for health monitoring.

In six months:
If you are wondering “where does a raw BirdNET detection get turned into a
standard event and actually leave the node?”, this is the file. Everything
north of this module is about BirdNET and sensors; everything south is about
storage, visualization, and long-term analysis.
"""

from __future__ import annotations

from typing import Any, Dict
import logging

# Dispatcher imports only the manager and the Wi-Fi sender, as designed.
from scripts.node.birdnet_lite_manager import BirdDetection, build_event_from_detection
from scripts.node.send_over_wifi import send_event

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

    This function takes a raw detection triple (bird_id, species_name,
    confidence), builds a BirdDetection, converts it into a complete event
    using the manager, and then forwards that event over Wi-Fi.

    Args:
        bird_id: Short ID or code for the species (e.g., 'AMRO').
        species_name: Human-readable common name (e.g., 'American Robin').
        confidence: Model confidence in [0.0, 1.0].

    Returns:
        The full event dictionary that was sent. This is useful for testing
        and for any upstream code that wants to inspect or log the event
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

    # Send over Wi-Fi (fire-and-forget for now).
    try:
        send_event(event)
        logger.info(
            "Event dispatched over Wi-Fi for event_id=%s",
            event.get("event_id"),
        )
    except Exception as exc:
        logger.exception(
            "Failed to send event over Wi-Fi for event_id=%s: %s",
            event.get("event_id"),
            exc,
        )
        # For now we just log; future versions might re-queue or persist.
        raise

    logger.debug("dispatch_detection() completed for event_id=%s", event.get("event_id"))
    return event


# ---------------------------------------------------------------------------
# Standalone debug/demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Running dispatcher.py as a script for debug/demo.")

    # Example: one fake detection flowing through the entire pipeline.
    try:
        event = dispatch_detection(
            bird_id="AMRO",
            species_name="American Robin",
            confidence=0.91,
        )
        print("Dispatched event dictionary:")
        for key, value in event.items():
            print(f"{key}: {value}")
    except Exception as exc:
        logger.exception("Dispatcher demo failed: %s", exc)
