# -*- coding: utf-8 -*-

"""
server_dispatcher.py

Master orchestrator for Backyard Bird Station server-side processing.

Responsibilities:
    - Start UDP listener
    - Receive decoded events from the Pi
    - Dispatch events to managers (database, GUI, alerts, etc.)
    - Keep running indefinitely

This script is the ONLY script that needs to run on PC startup.
"""

from __future__ import annotations

import logging
from typing import Dict, Tuple, Any

import udp_listener          # our driver module
import database              # our database manager (writes to working.db)
import create_database      # new script that creates all three SQLite DBs


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def configure_logging(level=logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


logger = logging.getLogger("birdstation.server_dispatcher")


# ---------------------------------------------------------------------------
# Event handling logic
# ---------------------------------------------------------------------------

def handle_event(event: Dict[str, Any], sender: Tuple[str, int]) -> None:
    """
    Callback for every incoming event from udp_listener.

    Parameters:
        event  - dict, decoded JSON from Pi
        sender - tuple (ip, port)
    """

    sender_ip, sender_port = sender
    event_id = event.get("event_id")

    logger.info(
        "Dispatcher received event_id=%s from %s:%d",
        event_id,
        sender_ip,
        sender_port,
    )

    # --------------------------------------------------------------
    # 1. Database storage (writes raw event into working.db)
    # --------------------------------------------------------------
    try:
        database.insert_event(event)
    except Exception:
        logger.exception(
            "Failed to store event_id=%s into SQLite database",
            event_id,
        )

    # --------------------------------------------------------------
    # 2. Future managers will plug in here:
    # --------------------------------------------------------------
    # gui_manager.handle_event(event)
    # alert_manager.handle_event(event)
    # species_stats_manager.handle_event(event)
    #
    # Each will follow the same pattern: clean separation of concerns.
    # --------------------------------------------------------------


# ---------------------------------------------------------------------------
# Main dispatcher loop
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()

    logger.info("=============================================")
    logger.info(" Backyard Bird Station - SERVER DISPATCHER ")
    logger.info("=============================================")

    # Initialize all SQLite databases (working, yearly, rarity)
    logger.info("Initializing SQLite databases (working/yearly/rarity)...")
    create_database.main()
    logger.info("SQLite databases initialized.")

    # Start UDP listener; this call NEVER RETURNS
    logger.info("Starting UDP event listener...")
    udp_listener.run_with_callback(handle_event)

    # If the listener ever returns (it should not):
    logger.error("udp_listener.run_with_callback() exited unexpectedly!")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nServer dispatcher stopped by user.\n")
