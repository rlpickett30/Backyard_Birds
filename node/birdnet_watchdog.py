# -*- coding: utf-8 -*-

# birdnet_watchdog.py

"""
Created on Fri Nov 28 17:55:18 2025

@author: lnpic

This module is the “BirdNET intelligence layer” for the backyard acoustic station.

Responsibilities (Version 1):
- Locate the BirdNET-Analyzer model files that were downloaded via kagglehub.
- Provide a simple, programmatic way for other modules to ask:
    - Where is the current model stored?
    - What directory does it live in?
- Stay completely separate from audio capture, event metadata, and dispatch logic.
  Its only job right now is to know “where BirdNET lives on disk.”

Debugging notes:
- Uses the standard logging library with logger name `birdstation.watchdog`.
- When run directly (`python birdnet_watchdog.py`), it will configure logging
  at DEBUG level and print the discovered model information.
- When imported, it is silent unless the application configures logging.

Future versions (Version 2+):
- Use the Python `watchdog` library to monitor the model cache directory.
- Detect when model files or species lists are added/updated.
- Notify birdnet_lite_manager.py so events can include an accurate `model_version`
  and the system can adapt to model or taxonomy changes over time.

In six months:
If you are wondering “where do we figure out which BirdNET model we are using,
and where do we watch for updates?”, this is the place. The rest of the node
code should treat this module as the single source of truth for BirdNET model
location and basic metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence
import logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.watchdog")

# ---------------------------------------------------------------------------
# Model discovery configuration
# ---------------------------------------------------------------------------

# File extensions that likely indicate a BirdNET model file.
MODEL_EXTS: Sequence[str] = (".h5", ".tflite", ".onnx", ".keras")

# Candidate cache roots where kagglehub / BirdNET-Analyzer might store models.
CACHE_CANDIDATES = [
    Path.home() / ".cache" / "kagglehub",
    Path.home() / ".cache" / "birdnet",
    Path.home() / ".cache",
]


@dataclass(frozen=True)
class ModelInfo:
    """Minimal information about the BirdNET model on disk."""
    model_file: Path
    model_dir: Path

    def to_dict(self) -> dict:
        return {
            "model_file": str(self.model_file),
            "model_dir": str(self.model_dir),
        }


@lru_cache(maxsize=1)
def locate_model() -> ModelInfo:
    """
    Search common cache directories for a BirdNET model file.

    Returns:
        ModelInfo with the first matching model file and its parent directory.

    Raises:
        FileNotFoundError if no model can be located in the expected cache roots.
    """
    logger.debug("Starting model discovery in cache candidates: %s", CACHE_CANDIDATES)

    for root in CACHE_CANDIDATES:
        logger.debug("Checking cache root: %s", root)
        if not root.exists():
            logger.debug("  → Root does not exist, skipping.")
            continue

        # Walk the tree once; stop as soon as we find something that looks like a model.
        for path in root.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.lower() in MODEL_EXTS and "birdnet" in path.name.lower():
                logger.debug("  → Model candidate found: %s", path)
                info = ModelInfo(model_file=path, model_dir=path.parent)
                logger.info("BirdNET model located: %s", info.to_dict())
                return info

    logger.error(
        "Failed to locate a BirdNET model file in cache roots: %s",
        [str(p) for p in CACHE_CANDIDATES],
    )
    raise FileNotFoundError(
        "Could not locate a BirdNET model file in the expected cache directories. "
        "Has BirdNET-Analyzer been run at least once to trigger a model download?"
    )


def get_model_info() -> dict:
    """
    Convenience wrapper that returns the current ModelInfo as a plain dict.
    Useful for logging, debugging, or attaching to events.
    """
    info = locate_model().to_dict()
    logger.debug("get_model_info() returning: %s", info)
    return info


if __name__ == "__main__":
    # Simple manual test:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Running birdnet_watchdog.py as a script for debug/demo.")

    try:
        info = get_model_info()
        print("BirdNET model information:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    except FileNotFoundError as exc:
        logger.exception("Model discovery failed: %s", exc)
