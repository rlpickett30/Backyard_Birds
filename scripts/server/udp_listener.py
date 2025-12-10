# -*- coding: utf-8 -*-

"""
udp_listener.py

UDP listener module for Backyard Bird Station events.

This module exposes two main entry points:

    udp_event_stream(...)
        -> yields (event_dict, (sender_ip, sender_port)) forever.

    run_with_callback(callback, ...)
        -> calls `callback(event_dict, (sender_ip, sender_port))`
           for each valid event, and never returns.

It is designed to be imported and driven by server_dispatcher.py.
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Any, Dict, Iterator, Tuple

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
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("birdstation.udp_listener")


# ---------------------------------------------------------------------------
# Core listener API
# ---------------------------------------------------------------------------

def udp_event_stream(
    host: str = LISTEN_HOST,
    port: int = LISTEN_PORT,
) -> Iterator[Tuple[Dict[str, Any], Tuple[str, int]]]:
    """
    Yield decoded JSON events from a UDP socket forever.

    Each yielded item is (event_dict, (sender_ip, sender_port)).

    Any packet that cannot be decoded as UTF-8 or JSON is logged and skipped.
    This function never raises on bad packets.
    """
    addr: Tuple[str, int] = (host, port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(addr)

    logger.info("UDP listener bound on %s:%d", host, port)

    while True:
        data, sender = sock.recvfrom(MAX_PACKET_SIZE)
        sender_ip, sender_port = sender

        logger.debug(
            "Packet received from %s:%d (%d bytes)",
            sender_ip,
            sender_port,
            len(data),
        )

        # Decode UTF-8.
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            logger.warning(
                "Dropping packet from %s:%d: invalid UTF-8.",
                sender_ip,
                sender_port,
            )
            continue

        # Parse JSON.
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Dropping packet from %s:%d: invalid JSON. Raw text (truncated): %r",
                sender_ip,
                sender_port,
                text[:200],
            )
            continue

        if not isinstance(obj, dict):
            logger.warning(
                "Dropping packet from %s:%d: JSON root is %s, expected object.",
                sender_ip,
                sender_port,
                type(obj).__name__,
            )
            continue

        yield obj, sender


def run_with_callback(
    callback,
    host: str = LISTEN_HOST,
    port: int = LISTEN_PORT,
) -> None:
    """
    Convenience helper: drive the event stream and invoke a callback.

    Args:
        callback: Function taking (event_dict, (sender_ip, sender_port)).
    """
    for event, sender in udp_event_stream(host=host, port=port):
        try:
            callback(event, sender)
        except Exception:
            logger.exception("Error while handling event from %s:%d", *sender)
            # Keep listening; do not let a bad handler kill the listener.


# ---------------------------------------------------------------------------
# Optional standalone debug mode
# ---------------------------------------------------------------------------

def configure_logging(level: int = logging.INFO) -> None:
    """Simple root logger configuration for standalone testing."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


if __name__ == "__main__":
    # Debug harness: pretty-print events if you run this file directly.
    configure_logging()

    def _print_event(event: Dict[str, Any], sender: Tuple[str, int]) -> None:
        sender_ip, sender_port = sender
        logger.info("Event received from %s:%d", sender_ip, sender_port)
        print("\n=== New Event ===")
        print(json.dumps(event, indent=2, ensure_ascii=False))
        print("=================\n")

    run_with_callback(_print_event)
