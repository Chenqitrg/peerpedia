"""Layer 1: LAN node discovery and catalog sync.

Split by concern for maintainability:
- lan_protocol.py — YAML catalog serialization/parsing + heartbeat messages
- lan_network.py — UDP broadcaster + listener threads

All imports from ``peerpedia_core.workflow.lan`` continue to work.
"""

from peerpedia_core.workflow.lan_network import (  # noqa: F401
    start_udp_broadcaster,
    start_udp_listener,
)
from peerpedia_core.workflow.lan_protocol import (  # noqa: F401
    BROADCAST_ADDR,
    CATALOG_YAML_DELIMITER,
    HEARTBEAT_TYPE,
    build_heartbeat_message,
    catalog_to_yaml_string,
    parse_catalog_yaml,
    parse_heartbeat_message,
)

__all__ = [n for n in dir() if not n.startswith("_")]
