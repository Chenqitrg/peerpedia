"""Layer 1: LAN networking — UDP broadcaster and listener threads.

I/O and threading functions. Depends on lan_protocol for data format functions.
"""

from __future__ import annotations

import socket
import threading

from peerpedia_core.workflow.lan_protocol import (
    BROADCAST_ADDR,
    build_heartbeat_message,
    parse_heartbeat_message,
)


def start_udp_broadcaster(
    node_id: str,
    host: str,
    port: int,
    *,
    database_url: str = "",
    broadcast_port: int = 3690,
    interval: float = 3.0,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    """Start a background thread that sends UDP heartbeat broadcasts.

    Args:
        node_id: This node's unique ID.
        host: This node's IP address (for the heartbeat, not binding).
        port: This node's HTTP port.
        database_url: SQLite database URL for counting local articles.
        broadcast_port: UDP port for broadcasting.
        interval: Seconds between heartbeats.
        stop_event: Set to stop the broadcaster.

    Returns:
        The running Thread object.
    """
    if stop_event is None:
        stop_event = threading.Event()

    def _broadcast_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        while not stop_event.is_set():
            try:
                msg = build_heartbeat_message(
                    node_id=node_id,
                    host=host,
                    port=port,
                    articles_count=_count_local_articles(database_url),
                )
                sock.sendto(msg.encode("utf-8"), (BROADCAST_ADDR, broadcast_port))
            except Exception:
                pass  # Network not available -- retry next interval
            stop_event.wait(interval)

        sock.close()

    thread = threading.Thread(target=_broadcast_loop, daemon=True, name="peerpedia-udp-bcast")
    thread.start()
    return thread


def start_udp_listener(
    database_url: str,
    *,
    listen_port: int = 3690,
    stop_event: threading.Event | None = None,
) -> threading.Thread:
    """Start a background thread that listens for UDP heartbeat broadcasts.

    Received heartbeats are upserted into the local lan_nodes table.
    """
    from peerpedia_core.storage.db import get_engine, get_session, init_db, upsert_node

    if stop_event is None:
        stop_event = threading.Event()

    def _listen_loop():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", listen_port))
        except OSError:
            return  # Port already in use

        sock.settimeout(1.0)

        engine = get_engine(database_url)
        init_db(engine)

        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                msg = parse_heartbeat_message(data.decode("utf-8", errors="replace"))
                if msg is None:
                    continue

                # Ignore our own broadcasts
                self_id = _get_self_node_id(database_url)
                if self_id and msg["node_id"] == self_id:
                    continue

                session = get_session(engine)
                try:
                    upsert_node(
                        session,
                        node_id=msg["node_id"],
                        host=msg["host"],
                        port=msg["port"],
                        version=msg.get("version", "0.2.0"),
                        articles_count=msg.get("articles_count", 0),
                    )
                    session.commit()
                except Exception:
                    session.rollback()
                finally:
                    session.close()
            except socket.timeout:
                continue
            except Exception:
                continue

        sock.close()

    thread = threading.Thread(target=_listen_loop, daemon=True, name="peerpedia-udp-listen")
    thread.start()
    return thread


def _count_local_articles(database_url: str) -> int:
    """Count local articles for heartbeat."""
    if not database_url:
        return 0
    try:
        from peerpedia_core.storage.db import get_engine, get_session, init_db, list_articles
        engine = get_engine(database_url)
        init_db(engine)
        session = get_session(engine)
        try:
            return len(list_articles(session, limit=10000))
        finally:
            session.close()
    except Exception:
        return 0


def _get_self_node_id(database_url: str) -> str | None:
    """Get this node's own node_id from the database."""
    try:
        from peerpedia_core.storage.db import get_engine, get_online_nodes, get_session, init_db
        engine = get_engine(database_url)
        init_db(engine)
        session = get_session(engine)
        try:
            nodes = get_online_nodes(session, timeout_seconds=86400)
            for n in nodes:
                if bool(n.is_self):
                    return n.node_id
            return None
        finally:
            session.close()
    except Exception:
        return None
