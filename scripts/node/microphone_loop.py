# -*- coding: utf-8 -*-

# microphone_loop.py

"""
Created on Fri Nov 28 19:16:05 2025

@author: Lee Pickett

Version 0: Live microphone detection loop.

This script:
1. Records 3 seconds of audio from the default USB microphone.
2. Saves it as temp.wav.
3. Runs BirdNET-Analyzer on it.
4. Parses detections and sends them into dispatcher.
5. Repeats forever.

Designed for rapid testing using played-back bird sounds.
"""

from __future__ import annotations

import csv
import logging
import subprocess
import time
from pathlib import Path

from dispatcher import dispatch_detection


logger = logging.getLogger("birdstation.micloop")


# -----------------------------
# RECORD AUDIO
# -----------------------------
def record_audio(out_path: Path, duration_sec: float = 3.0):
    """
    Records raw audio from the default microphone using arecord.
    Assumes a USB audio interface.
    """

    cmd = [
        "arecord",
        "-f", "S16_LE",
        "-r", "48000",
        "-c", "1",
        "-d", str(duration_sec),
        str(out_path),
    ]

    logger.debug("Recording audio: %s", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        logger.error("arecord failed: %s", exc)
        return False

    return True


# -----------------------------
# RUN BIRDNET
# -----------------------------
def analyze_audio(wav_path: Path):
    """
    Runs BirdNET-Analyzer on a WAV file and returns list of detections.
    Each detection is (species_code, species_name, confidence).
    """

    cmd = [
        "python3", "-m", "birdnet_analyzer.analyze",
        str(wav_path),
        "--rtype", "csv",
        "--combine_results"
    ]

    logger.debug("Running BirdNET-Analyzer: %s", " ".join(cmd))

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        logger.error("BirdNET analysis failed: %s", exc)
        return []

    # Find CSV output
    out_dir = Path(f"{wav_path}.results")
    if not out_dir.exists():
        out_dir = Path(str(wav_path))

    csv_files = list(out_dir.glob("*.csv"))
    if not csv_files:
        logger.debug("No CSV results found.")
        return []

    detections = []
    csv_file = csv_files[0]

    with csv_file.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                code = row["Species Code"]
                species = row["Common Name"]
                conf = float(row["Confidence"])
            except KeyError:
                continue

            detections.append((code, species, conf))

    return detections


# -----------------------------
# MAIN LOOP
# -----------------------------
def main():
    wav_path = Path("/home/node0/birdstation/temp.wav")

    logger.info("Starting live microphone loop.")
    logger.info("Playing a goose or raven call near the mic should produce detections.")

    while True:
        # 1. Record
        ok = record_audio(wav_path)
        if not ok:
            time.sleep(1)
            continue

        # 2. Analyze
        detections = analyze_audio(wav_path)

        # 3. Dispatch detections
        for code, species, conf in detections:
            logger.info("Detected: %s (%s) %.2f", species, code, conf)
            dispatch_detection(code, species, conf)

        # 4. Small pause before next loop
        time.sleep(0.2)


if __name__ == "__main__":
    logging.b
