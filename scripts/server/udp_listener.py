# -*- coding: utf-8 -*-

"""
udp_listener.py

Simple UDP listener for Backyard Bird Station events.

This script:
- Binds to a UDP port on your PC.
- Waits for JSON-encoded events from the Pi (send_over_wifi.py).
- Prints each event to the console in a readable format.
- Never crashes on bad packets; it logs and continues.

Run it on your PC, then trigger detections on the Pi.
You should see each dispatched event appear here.
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Tuple

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Listen on all interfaces so the Pi can reach us.
LISTEN_HOST: str = "0.0.0.0"

# This must match DEST_PORT in send_over_wifi.py on the Pi.
LISTEN_PORT: int = 50555

# Maximum packet size (bytes). 65535 is safe for UDP.
MAX_PACKET_SIZE: int = 65535


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.udp_listener")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# Core listener logic
# ---------------------------------------------------------------------------

def start_listener(host: str = LISTEN_HOST, port: int = LISTEN_PORT) -> None:
    """
    Start a blocking UDP listener that prints incoming JSON events.

    Args:
        host: IP address to bind to (use "0.0.0.0" for all interfaces).
        port: UDP port to listen on (must match the Pi's DEST_PORT).
    """
    addr: Tuple[str, int] = (host, port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(addr)

    logger.info("UDP listener started on %s:%d", host, port)
    logger.info("Waiting for events from the Pi...")

    while True:
        data, sender = sock.recvfrom(MAX_PACKET_SIZE)
        sender_ip, sender_port = sender

        logger.info("Packet received from %s:%d (%d bytes)", sender_ip, sender_port, len(data))

        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            logger.warning("Packet is not valid UTF-8; showing raw bytes.")
            print(data)
            continue

        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Packet is not valid JSON; showing raw text.")
            print(text)
            continue

        # Pretty-print the JSON event.
        print("\n=== New Event ===")
        print(json.dumps(obj, indent=2, ensure_ascii=False))
        print("=================\n")


if __name__ == "__main__":
    configure_logging()
    start_listener()
