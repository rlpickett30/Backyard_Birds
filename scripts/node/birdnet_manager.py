# -*- coding: utf-8 -*-

# birdnet_manager.py
"""
Backyard_Birds – BirdNET manager

This module is the "mini dispatcher" for BirdNET detections. It sits between:

    microphone_loop   →  birdnet_manager  →  dispatcher / send_over_wifi
          (audio)            (events)              (transport)

Responsibilities:
- Receive paths to recorded audio chunks from microphone_loop.
- Run BirdNET analysis via birdnet_analyzer.analyze_wav().
- Apply simple policies (confidence threshold, max events per chunk).
- Wrap each selected detection in an EventShell from birdnet_metadata.
- Emit completed event dictionaries to an event_callback supplied
  by the top-level dispatcher.

Public API:
    process_chunk(audio_path, event_callback) -> list[event_dict]
    run_live_loop(event_callback)             -> None
"""

from __future__ import annotations

from typing import Callable, Dict, List
import logging
import pathlib

import microphone_loop
import birdnet_analyzer
from birdnet_metadata import new_event_shell

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.birdnet_manager")

# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------

# Minimum BirdNET confidence required to emit an event.
MIN_EMIT_CONFIDENCE: float = 0.25

# Maximum number of events to emit per audio chunk.
# For example, 1 = top-1 species per chunk, 3 = top-3 species, etc.
MAX_EVENTS_PER_CHUNK: int = 1

# Optional flag to include raw detection list in each event (for debugging).
INCLUDE_ALL_DETECTIONS: bool = False


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _build_event_from_detection(detection: Dict, audio_path: pathlib.Path) -> Dict:
    """
    Combine an EventShell with one BirdNET detection to form a full event dict.

    The detection dict is expected to have keys:
        common_name, species_code, confidence, start_time, end_time.
    """
    shell = new_event_shell()  # from birdnet_metadata
    shell_dict = shell.to_dict()

    bird_block = {
        "species_code": detection["species_code"],
        "common_name": detection["common_name"],
        "confidence": float(detection["confidence"]),
        "start_time": float(detection["start_time"]),
        "end_time": float(detection["end_time"]),
    }

    audio_block = {
        "file": str(audio_path),
    }

    model_block = {
        "source": "birdnet_analyzer/birdnetlib",
        "min_conf": birdnet_analyzer.MIN_CONF,
        "lat": birdnet_analyzer.LAT,
        "lon": birdnet_analyzer.LON,
        "week": birdnet_analyzer.WEEK,
    }

    event: Dict = {
        **shell_dict,
        "event_type": "birdnet_detection",
        "bird": bird_block,
        "audio": audio_block,
        "model": model_block,
    }

    return event


# ---------------------------------------------------------------------------
# Public manager API
# ---------------------------------------------------------------------------

def process_chunk(
    audio_path: pathlib.Path,
    event_callback: Callable[[Dict], None],
) -> List[Dict]:
    """
    Analyze one recorded audio chunk and emit events via event_callback.

    Args:
        audio_path:
            Path to the WAV file produced by microphone_loop.
        event_callback:
            Function that accepts a completed event dict (for example,
            dispatcher → send_over_wifi.send_event).

    Returns:
        List of event dictionaries that were emitted (useful for testing).
    """
    logger.info("Processing audio chunk: %s", audio_path)

    # Run BirdNET analysis.
    detections = birdnet_analyzer.analyze_wav(audio_path)
    logger.info("Raw detections from analyzer: %d", len(detections))

    if not detections:
        logger.info("No detections returned for chunk: %s", audio_path)
        return []

    # Filter by confidence.
    filtered = [
        d for d in detections
        if float(d["confidence"]) >= MIN_EMIT_CONFIDENCE
    ]
    logger.info(
        "Detections above MIN_EMIT_CONFIDENCE=%.2f: %d",
        MIN_EMIT_CONFIDENCE,
        len(filtered),
    )

    if not filtered:
        logger.info("All detections below confidence threshold; no events emitted.")
        return []

    # Take top-N detections (detections are already sorted by confidence
    # in birdnet_analyzer.analyze_wav()).
    selected = filtered[:MAX_EVENTS_PER_CHUNK]
    logger.info(
        "Selected %d detections for event emission (MAX_EVENTS_PER_CHUNK=%d).",
        len(selected),
        MAX_EVENTS_PER_CHUNK,
    )

    # Optionally keep all detections for debugging/inspection.
    all_detections_block = detections if INCLUDE_ALL_DETECTIONS else None

    emitted_events: List[Dict] = []

    for det in selected:
        event = _build_event_from_detection(det, audio_path)
        if all_detections_block is not None:
            event["debug_all_detections"] = all_detections_block

        logger.info(
            "Emitting event for species=%s (code=%s, conf=%.3f, event_id=%s)",
            det["common_name"],
            det["species_code"],
            det["confidence"],
            event.get("event_id"),
        )

        # Fire-and-forget callback; caller decides what to do (send over Wi-Fi, log, etc.).
        try:
            event_callback(event)
        except Exception as exc:
            logger.exception(
                "event_callback raised an exception for event_id=%s: %s",
                event.get("event_id"),
                exc,
            )

        emitted_events.append(event)

    logger.debug(
        "process_chunk() completed for %s; events emitted: %d",
        audio_path,
        len(emitted_events),
    )
    return emitted_events


def run_live_loop(event_callback: Callable[[Dict], None]) -> None:
    """
    High-level entry point for the BirdNET pipeline.

    This function:
        - Starts the microphone loop.
        - For each recorded chunk, runs BirdNET analysis.
        - Builds events and hands them to event_callback.

    Under normal operation this does not return; use Ctrl+C to stop.
    """

    logger.info("Starting BirdNET manager live loop.")
    logger.info(
        "Policy: MIN_EMIT_CONFIDENCE=%.2f, MAX_EVENTS_PER_CHUNK=%d",
        MIN_EMIT_CONFIDENCE,
        MAX_EVENTS_PER_CHUNK,
    )

    def _on_audio_chunk(audio_path: pathlib.Path) -> None:
        logger.debug("Received audio chunk from microphone_loop: %s", audio_path)
        process_chunk(audio_path, event_callback)

    microphone_loop.run_live_loop(_on_audio_chunk)

