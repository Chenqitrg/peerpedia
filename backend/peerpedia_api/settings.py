# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Centralised runtime settings — DB path, environment, etc."""
from __future__ import annotations

import os
from pathlib import Path


def get_database_url() -> str:
    """Return the SQLAlchemy database URL.

    Priority:
    1. ``PEERPEDIA_DB`` environment variable (explicit override)
    2. ``PEERPEDIA_HOME`` / peerpedia.db (custom data directory)
    3. ``~/.peerpedia/peerpedia.db`` (default)
    """
    explicit = os.environ.get("PEERPEDIA_DB")
    if explicit:
        return explicit

    data_dir = Path(os.environ.get("PEERPEDIA_HOME", Path.home() / ".peerpedia"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'peerpedia.db'}"
