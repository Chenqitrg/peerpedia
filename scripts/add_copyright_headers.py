#!/usr/bin/env python3
"""Add SPDX copyright headers to source files."""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEADERS = {
    ".py": (
        "# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors\n# SPDX-License-Identifier: CC-BY-NC-SA-4.0\n"
    ),
    ".ts": (
        "// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors\n"
        "// SPDX-License-Identifier: CC-BY-NC-SA-4.0\n"
    ),
    ".vue": (
        "<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->\n"
        "<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->\n"
    ),
    ".rs": (
        "// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors\n"
        "// SPDX-License-Identifier: CC-BY-NC-SA-4.0\n"
    ),
    ".js": (
        "// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors\n"
        "// SPDX-License-Identifier: CC-BY-NC-SA-4.0\n"
    ),
    ".html": (
        "<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->\n"
        "<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->\n"
    ),
}

SKIP_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "target",
    "dist",
    ".superpowers",
    ".claude",
}

SKIP_EXTENSIONS = {".json", ".toml", ".lock", ".css", ".svg", ".png", ".jpg", ".ico", ".md"}


def has_header(content, ext):
    """Check if file already has the SPDX header."""
    header = HEADERS[ext]
    first_line = header.split("\n")[0]
    return first_line in content


def add_header(filepath):
    ext = os.path.splitext(filepath)[1]
    if ext not in HEADERS:
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if has_header(content, ext):
        return False

    header = HEADERS[ext]

    # Handle shebang
    if content.startswith("#!"):
        end_of_shebang = content.index("\n") + 1
        content = content[:end_of_shebang] + "\n" + header + "\n" + content[end_of_shebang:]
    # Handle Vue/HTML with <template> or <script> at start
    elif ext == ".html" and content.strip().startswith("<!DOCTYPE"):
        end_of_doctype = content.index(">") + 1
        content = content[:end_of_doctype] + "\n" + header + "\n" + content[end_of_doctype:]
    elif ext == ".vue" and content.strip().startswith("<"):
        content = header + "\n" + content
    else:
        content = header + "\n" + content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return True


def main():
    added = 0
    skipped = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            ext = os.path.splitext(filename)[1]
            if ext in SKIP_EXTENSIONS:
                continue
            if ext not in HEADERS:
                continue

            filepath = os.path.join(root, filename)
            if add_header(filepath):
                added += 1
                print(f"  + {os.path.relpath(filepath, PROJECT_ROOT)}")
            else:
                skipped += 1

    print(f"\nDone: {added} files updated, {skipped} already had headers.")


if __name__ == "__main__":
    main()
