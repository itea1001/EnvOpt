#!/usr/bin/env python3
"""Replace an inclusive 1-based line range with stdin.

Use this for small multi-line edits where shell quoting makes sed fragile.
It can also insert before START by passing END as START - 1. It fails on
invalid paths/ranges and only writes after reading the whole file.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: replace_lines.py PATH START END < new_text", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    if start < 1 or end < start - 1:
        print(f"invalid range: {start}-{end}", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 2
    lines = path.read_text().splitlines(keepends=True)
    if end > len(lines):
        print(f"range ends at {end}, but {path} has {len(lines)} lines", file=sys.stderr)
        return 2
    if start > len(lines) + 1:
        print(f"start is {start}, but {path} has {len(lines)} lines", file=sys.stderr)
        return 2
    replacement = sys.stdin.read()
    if replacement and not replacement.endswith("\n"):
        replacement += "\n"
    if end == start - 1:
        path.write_text("".join([*lines[: start - 1], replacement, *lines[start - 1 :]]))
    else:
        path.write_text("".join([*lines[: start - 1], replacement, *lines[end:]]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
