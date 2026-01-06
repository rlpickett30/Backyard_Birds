"""
microphone_loop.py

Driver-level script responsible ONLY for interacting with the USB microphone
and producing recorded audio chunks for further processing.

This module does NOT run BirdNET, does NOT build events, and does NOT
communicate over UDP. It is a simple, testable hardware interface.

Public API:
    run_live_loop(callback)
"""

import subprocess
import pathlib
import time

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

BASE_DIR = pathlib.Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
AUDIO_PATH = RUNTIME_DIR / "mic_chunk.wav"

ARECORD_DEVICE = "plughw:CARD=Device,DEV=0"
ARECORD_RATE = 48000
ARECORD_CHANNELS = 1
ARECORD_FORMAT = "S16_LE"
CHUNK_SECONDS = 5


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

def record_chunk():
    """Record a single audio chunk and return the path to the WAV file."""
    print("[mic] Preparing to record audio chunk...")

    # Ensure runtime directory exists
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    # Remove stale audio file if present
    if AUDIO_PATH.exists():
        print(f"[mic] Removing previous audio file: {AUDIO_PATH}")
        AUDIO_PATH.unlink()

    cmd = [
        "arecord",
        "-D", ARECORD_DEVICE,
        "-f", ARECORD_FORMAT,
        "-r", str(ARECORD_RATE),
        "-c", str(ARECORD_CHANNELS),
        "-d", str(CHUNK_SECONDS),
        str(AUDIO_PATH),
    ]

    print(f"[mic] Running arecord for {CHUNK_SECONDS} seconds...")
    t0 = time.perf_counter()

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("[mic] ERROR during recording:", e)
        return None

    t1 = time.perf_counter()
    print(f"[mic] Recording complete. Duration: {t1 - t0:.2f}s")

    # Confirm file was created
    if not AUDIO_PATH.exists():
        print("[mic] ERROR: Audio file was not created!")
        return None

    file_size = AUDIO_PATH.stat().st_size
    print(f"[mic] Output file: {AUDIO_PATH} ({file_size} bytes)")

    return AUDIO_PATH


# ---------------------------------------------------------------------
# Public Loop
# ---------------------------------------------------------------------

def run_live_loop(callback):
    """
    Continuously record audio chunks and deliver each chunk’s path to the callback.

    callback signature:
        callback(audio_path: pathlib.Path)

    The callback should NOT return "detections" or events; it should simply
    process the audio file (manager-level responsibility).
    """

    print("[mic] Microphone loop started. Press Ctrl+C to stop.")

    try:
        while True:
            audio_file = record_chunk()

            if audio_file is None:
                print("[mic] Skipping callback due to recording error.")
                continue

            print("[mic] Delivering audio chunk to callback...")
            try:
                callback(audio_file)
            except Exception as e:
                print("[mic] ERROR inside callback:", e)

            print("[mic] Loop cycle complete. Preparing for next chunk...\n")

    except KeyboardInterrupt:
        print("\n[mic] Microphone loop stopped by user.")

