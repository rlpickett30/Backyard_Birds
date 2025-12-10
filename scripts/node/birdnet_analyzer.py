"""
birdnet_analyzer.py

Clean rewrite for Backyard_Birds.
Wraps birdnetlib and produces stable, normalized detection dictionaries.

Output Format (guaranteed):
{
    "common_name": str,
    "species_code": str,
    "confidence": float,
    "start_time": float,
    "end_time": float
}
"""

from __future__ import annotations

import pathlib
import time
from typing import List, Dict

from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer

# ----------------------------------------------------------------------
# BirdNET Configuration
# ----------------------------------------------------------------------

LAT = 37.2753
LON = -107.8801
WEEK = 48
MIN_CONF = 0.01          # Let manager enforce stricter confidence later

# ----------------------------------------------------------------------
# Initialize analyzer once (expensive)
# ----------------------------------------------------------------------

print("[analyzer] Initializing BirdNET model...")
_ANALYZER = Analyzer()
print("[analyzer] BirdNET model is ready.")


# ----------------------------------------------------------------------
# Helper: Create a stable species_code from common name
# ----------------------------------------------------------------------

def _make_species_code(common_name: str) -> str:
    """
    Convert common name into a consistent 6–8 character species code.

    Examples:
        Canada Goose     → cangoo
        American Robin   → amrobin
        Dark-eyed Junco  → darkey
    """
    name = common_name.lower().replace("-", " ").replace("_", " ")
    parts = name.split()

    if len(parts) == 1:
        # Single word name:
        # “Mallard” → mallar
        return parts[0][:6]

    if len(parts) >= 2:
        # Two-word name:
        # “American Robin” → amrobin
        return parts[0][:2] + parts[1][:4]

    return common_name.lower().replace(" ", "")[:6]


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def analyze_wav(audio_path: pathlib.Path | str) -> List[Dict]:
    """
    Run BirdNET on the given WAV file and return normalized detection dicts.
    """

    path = pathlib.Path(audio_path)

    print(f"[analyzer] Analyzing file: {path}")

    if not path.exists():
        print(f"[analyzer] ERROR: File does not exist: {path}")
        return []

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
        recording.analyze()

    except Exception as exc:
        print("[analyzer] ERROR during analysis:", exc)
        return []

    t1 = time.perf_counter()
    print(f"[analyzer] BirdNET raw count: {len(recording.detections)}")
    print(f"[analyzer] Analysis time: {t1 - t0:.2f} s")

    # ------------------------------------------------------------------
    # Normalize raw detections
    # ------------------------------------------------------------------

    normalized: List[Dict] = []

    for det in recording.detections:

        common = det.get("common_name")
        if not common:
            print("[analyzer] WARNING: Missing common_name in:", det)
            continue

        # Build species_code safely
        species_code = _make_species_code(common)

        try:
            nd = {
                "common_name": common,
                "species_code": species_code,
                "confidence": float(det.get("confidence", 0.0)),
                "start_time": float(det.get("start_time", 0.0)),
                "end_time": float(det.get("end_time", 0.0)),
            }
            normalized.append(nd)

        except Exception as exc:
            print("[analyzer] WARNING: Failed to normalize detection:", exc)
            print("          Raw detection:", det)

    normalized.sort(key=lambda d: d["confidence"], reverse=True)

    print(f"[analyzer] Normalized detections: {len(normalized)}")
    for d in normalized:
        print(
            f"    - {d['common_name']} ({d['species_code']})  "
            f"conf={d['confidence']:.3f}  "
            f"{d['start_time']:.1f}s–{d['end_time']:.1f}s"
        )

    return normalized

