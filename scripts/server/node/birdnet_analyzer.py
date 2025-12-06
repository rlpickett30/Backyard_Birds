"""
birdnet_analyzer.py

Wraps birdnetlib / BirdNET-Analyzer in a simple, reusable interface.

Responsibilities:
    - Initialize a single persistent Analyzer instance.
    - Run analysis on a given WAV file.
    - Return raw detection dictionaries (no node IDs, no UDP, no metadata).

Public API:
    analyze_wav(audio_path) -> list[dict]
"""

import pathlib
import time

from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

# These match your previous successful runs
LAT = 37.2753
LON = -107.8801
WEEK = 48          # week-of-year for species list
MIN_CONF = 0.25    # BirdNET confidence threshold (adjust later if desired)

# ---------------------------------------------------------------------
# Analyzer initialization
# ---------------------------------------------------------------------

print("[analyzer] Initializing BirdNET Analyzer (this may take a moment)...")
_ANALYZER = Analyzer()
print("[analyzer] BirdNET Analyzer ready.")


# ---------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------

def analyze_wav(audio_path) -> list[dict]:
    """
    Run BirdNET on the given WAV file and return a list of raw detections.

    Parameters
    ----------
    audio_path : str | pathlib.Path
        Path to the audio file to analyze.

    Returns
    -------
    detections : list[dict]
        Each detection has keys:
            - common_name   : str
            - species_code  : str
            - confidence    : float
            - start_time    : float (seconds)
            - end_time      : float (seconds)
    """
    path = pathlib.Path(audio_path)

    print(f"[analyzer] Requested analysis for: {path}")

    if not path.exists():
        print(f"[analyzer] ERROR: File does not exist: {path}")
        return []

    file_size = path.stat().st_size
    print(f"[analyzer] Input file size: {file_size} bytes")

    t0 = time.perf_counter()

    try:
        recording = Recording(
            _ANALYZER,
            str(path),
            lat=LAT,
            lon=LON,
            week_48=WEEK,
            min_conf=MIN_CONF,
        )

        print("[analyzer] Recording object created. Starting analysis...")
        recording.analyze()
        print("[analyzer] Raw detections from birdnetlib:",
              len(recording.detections))

    except Exception as e:
        print("[analyzer] ERROR during analysis:", e)
        return []

    t1 = time.perf_counter()
    print(f"[analyzer] Analysis finished in {t1 - t0:.2f} s.")

    # Normalize detections into a simple list of dicts
    detections: list[dict] = []
    for det in recording.detections:
        try:
            detections.append(
                {
                    "common_name": det["common_name"],
                    "species_code": det["species_code"],
                    "confidence": float(det["confidence"]),
                    "start_time": float(det["start_time"]),
                    "end_time": float(det["end_time"]),
                }
            )
        except KeyError as missing:
            print("[analyzer] WARNING: Missing key in detection:", missing)
            print("           Raw detection:", det)

    # Optional: sort by confidence descending to make manager logic easier
    detections.sort(key=lambda d: d["confidence"], reverse=True)

    print("[analyzer] Normalized detections:", len(detections))
    for d in detections:
        print(
            f"    - {d['common_name']} ({d['species_code']}) "
            f"conf={d['confidence']:.3f}  "
            f"{d['start_time']:.1f}s–{d['end_time']:.1f}s"
        )

    return detections
