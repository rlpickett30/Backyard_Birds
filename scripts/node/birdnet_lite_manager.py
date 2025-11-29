# -*- coding: utf-8 -*-

# birdnet_lite_manager.py

"""
Created on Fri Nov 28 18:30:00 2025

@author: Lee Pickett

This module sits between the BirdNET detection layer and the rest of the
Backyard Acoustic Monitor node. It takes “raw” BirdNET detections
(species + confidence), wraps them in an EventShell from birdnet_metadata,
optionally attaches BirdNET model information from birdnet_watchdog, and
produces a fully-formed event dictionary ready for dispatcher.py.

Responsibilities (Version 1):
- Accept a single detection payload containing:
    - bird_id (e.g., 'AMRO')
    - species_name (common name string)
    - confidence (float between 0 and 1)
- Create a fresh EventShell (event_id, node_id, timestamps, weather=None).
- Attach the detection under event["bird"].
- Attach BirdNET model information under event["model"] (if available).
- Return the complete event dictionary to the caller.

Future versions (Version 2+):
- Accept batched detections from a 3-second window and perform local
  aggregation (e.g., max-confidence per species, or top-N species).
- Attach additional analysis metadata (e.g., window_start, window_end,
  frequency band settings).
- Forward events directly to dispatcher.py and handle basic retry logic.

In six months:
If you are wondering “where does a raw BirdNET detection turn into one of
our standard event JSON objects?”, this is the file. All node-side code
should use this module rather than building event dicts by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict
import logging

# Local imports: these assume the project root is on PYTHONPATH and that you
# run modules like `python -m scripts.node.birdnet_lite_manager`.
from birdnet_metadata import new_event_shell
from birdnet_watchdog import get_model_info

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.manager")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BirdDetection:
    """
    Simple container for one BirdNET detection.

    Fields:
        bird_id: Short ID or code for the species (e.g., 'AMRO').
        species_name: Human-readable common name (e.g., 'American Robin').
        confidence: Model confidence in [0.0, 1.0].
    """
    bird_id: str
    species_name: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Core manager logic
# ---------------------------------------------------------------------------


def build_event_from_detection(detection: BirdDetection) -> Dict[str, Any]:
    """
    Combine a BirdDetection with an EventShell and BirdNET model info to
    produce a complete event dictionary.

    Args:
        detection: BirdDetection instance describing a single BirdNET result.

    Returns:
        A dictionary with, at minimum, the following structure:

        {
            "event_id": "...",
            "node_id": "yard_station_1",
            "timestamp_utc": "...",
            "local_time": "...",
            "weather": null,

            "bird": {
                "bird_id": "AMRO",
                "species_name": "American Robin",
                "confidence": 0.83
            },

            "model": {
                "model_file": "...",
                "model_dir": "..."
            }
        }
    """
    logger.debug("Building event from detection: %s", detection.to_dict())

    # Base event shell (identity + timestamps + weather placeholder).
    shell = new_event_shell().to_dict()
    logger.debug("Received EventShell from metadata: %s", shell)

    # BirdNET model information (location on disk).
    try:
        model_info = get_model_info()
        logger.debug("Model info from watchdog: %s", model_info)
    except FileNotFoundError as exc:
        # If model info cannot be found, log and proceed without it.
        logger.warning("Model info unavailable: %s", exc)
        model_info = None

    # Assemble the final event.
    event: Dict[str, Any] = {
        **shell,
        "bird": detection.to_dict(),
        "model": model_info,
    }

    logger.debug("Final event built: %s", event)
    return event


# ---------------------------------------------------------------------------
# Standalone debug/demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Running birdnet_lite_manager.py as a script for debug/demo.")

    # Create a fake detection to exercise the pipeline.
    fake_detection = BirdDetection(
        bird_id="AMRO",
        species_name="American Robin",
        confidence=0.83,
    )

    event = build_event_from_detection(fake_detection)
    print("Example event dictionary:")
    for key, value in event.items():
        print(f"{key}: {value}")
