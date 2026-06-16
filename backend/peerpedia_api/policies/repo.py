# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Repository security utilities — path traversal, symlink, and tar safety.

Used by ``routes/articles.py`` to validate git repos before reading,
forking, downloading, or compiling.
"""
from __future__ import annotations

import os
import tarfile
from pathlib import Path

from fastapi import HTTPException


def ensure_inside(base: Path, target: Path) -> Path:
    """Resolve *target* and verify it is inside *base*.

    Uses ``Path.relative_to()`` which is stricter than string-prefix
    matching — it correctly rejects ``../../`` escapes even when the
    prefix string happens to match.
    """
    base = base.resolve()
    target = target.resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path escapes repository")
    return target


def reject_symlinks(root: Path) -> None:
    """Raise 400 if *root* (or any descendant) is a symlink.

    Article repos must not contain symlinks — they can be used to
    escape the repo directory during source reads, compilation,
    or download.
    """
    root = root.resolve()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise HTTPException(
                status_code=400,
                detail=f"Symlinks not allowed in article repo: {path.relative_to(root)}",
            )


def safe_extract_tar(tar: tarfile.TarFile, target: Path) -> None:
    """Extract tar members into *target*, rejecting path-traversal and
    special files.

    Rejects:
    - Paths that escape *target* (``../``, absolute)
    - Symlinks / hardlinks
    - Device files / FIFOs
    """
    target = target.resolve()

    for member in tar.getmembers():
        member_path = (target / member.name).resolve()
        try:
            member_path.relative_to(target)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Unsafe tar path in repo_bundle",
            )
        if member.issym() or member.islnk():
            raise HTTPException(
                status_code=400,
                detail="Symlinks are not allowed in repo_bundle",
            )
        if member.isdev() or member.isfifo():
            raise HTTPException(
                status_code=400,
                detail="Special files are not allowed in repo_bundle",
            )

    tar.extractall(target)
