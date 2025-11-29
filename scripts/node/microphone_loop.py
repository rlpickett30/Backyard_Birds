# microphone_loop.py

"""
Live microphone → BirdNET-Analyzer → dispatcher loop (helper module).

This module does NOT run on its own. It exposes a single entry point:

    run_live_loop(dispatch_fn, arecord_device="hw:1,0")

`dispatch_fn` is a callback that will be invoked as:

    dispatch_fn(species_code, species_name, confidence)

Dispatcher stays the main loop and passes in its own dispatch_detection()
function.
"""

from __future__ import annotations

import csv
import logging
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Tuple

logger = logging.getLogger("birdstation.microphone_loop")

# Where to store temporary audio and CSVs.
WORK_DIR = Path("/home/node0/birdstation/runtime")
WORK_DIR.mkdir(parents=True, exist_ok=True)

# Temporary WAV file path.
WAV_PATH = WORK_DIR / "mic_chunk.wav"

# Default recording length in seconds.
CHUNK_SECONDS = 3.0

# Default ALSA device string; dispatcher can override at runtime.
DEFAULT_ARECORD_DEVICE = "hw:1,0"

# Minimum confidence; we want everything.
MIN_CONF = 0.0


def record_chunk(arecord_device: str) -> bool:
    """
    Record a short audio chunk from the USB microphone using `arecord`.

    Returns True if recording succeeded, False otherwise.
    """
    cmd = [
        "arecord",
        "-D", arecord_device,
        "-f", "S16_LE",
        "-r", "48000",
        "-c", "1",
        "-d", str(CHUNK_SECONDS),
        str(WAV_PATH),
    ]

    logger.debug("Recording audio chunk: %s", " ".join(cmd))

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("arecord failed: %s", exc)
        return False

    return True


def run_birdnet_on_chunk() -> List[Tuple[str, str, float]]:
    """
    Run BirdNET-Analyzer on WAV_PATH and return a list of detections.

    Each detection is a tuple: (species_code, species_name, confidence).
    """
    if not WAV_PATH.exists():
        logger.warning("WAV file %s does not exist; skipping analysis.", WAV_PATH)
        return []

    cmd = [
        "python3",
        "-m",
        "birdnet_analyzer.analyze",
        str(WAV_PATH),
        "--rtype", "csv",
        "--min_conf", str(MIN_CONF),
    ]

    logger.debug("Running BirdNET-Analyzer: %s", " ".join(cmd))

    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("BirdNET-Analyzer failed: %s", exc)
        return []

    # Look for any CSV in WORK_DIR with the newest modification time.
    csv_files = sorted(
        WORK_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not csv_files:
        logger.debug("No CSV results found in %s.", WORK_DIR)
        return []

    csv_path = csv_files[0]
    logger.debug("Using CSV result: %s", csv_path)

    detections: List[Tuple[str, str, float]] = []

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                code = row.get("Species Code") or row.get("Species", "")
                species = row.get("Common Name") or row.get("CommonName", "")
                conf = float(row.get("Confidence", "0.0"))
            except Exception:
                continue

            detections.append((code, species, conf))

    return detections


def run_live_loop(
    dispatch_fn: Callable[[str, str, float], None],
    arecord_device: str = DEFAULT_ARECORD_DEVICE,
) -> None:
    """
    Main live loop for microphone capture and BirdNET analysis.

    Args:
        dispatch_fn: callback that accepts (species_code, species_name, confidence).
        arecord_device: ALSA device string, for example "hw:1,0".
    """
    logger.info("Starting live microphone detection loop.")
    logger.info("Recording %.1f s chunks from device %s", CHUNK_SECONDS, arecord_device)
    logger.info("Play bird calls near the mic; detections will be sent to dispatcher.")

    while True:
        # 1. Record audio
        if not record_chunk(arecord_device):
            logger.warning("Recording failed; retrying in 2 seconds.")
            time.sleep(2.0)
            continue

        # 2. Analyze audio with BirdNET
        detections = run_birdnet_on_chunk()

        # 3. Dispatch each detection
        if not detections:
            logger.debug("No detections in this chunk.")
        else:
            for code, species, conf in detections:
                logger.info(
                    "Detected species=%s (code=%s) with confidence=%.3f",
                    species,
                    code,
                    conf,
                )
                dispatch_fn(code, species, conf)

        # 4. Small pause to avoid hammering the CPU
        time.sleep(0.2)
