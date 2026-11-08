#!/usr/bin/env python3
"""Run focused Tenacity tests based on changed files.

This helper never converts a failing test run into success. Its exit status is
the pytest exit status. When it cannot determine a narrower target, it runs the
full test suite.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()


def run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def changed_files() -> list[str]:
    proc = run_capture(["git", "diff", "--name-only"])
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def existing(paths: list[str]) -> list[str]:
    return [p for p in paths if (ROOT / p).exists()]


def targets_from_changes(paths: list[str]) -> list[str]:
    target_paths: list[str] = []
    keywords: set[str] = set()
    source_changes = [p for p in paths if p.startswith("tenacity/") and p.endswith(".py")]
    test_changes = [p for p in paths if p.startswith("tests/") and p.endswith(".py")]
    target_paths.extend(test_changes)
    for path in source_changes:
        if path.startswith("tenacity/asyncio/"):
            target_paths.extend(existing(["tests/test_asyncio.py"]))
            keywords.update(["async", "retry"])
        elif path == "tenacity/tornadoweb.py":
            target_paths.extend(existing(["tests/test_tornado.py"]))
        elif path == "tenacity/wait.py":
            target_paths.extend(existing(["tests/test_tenacity.py"]))
            keywords.add("wait")
        elif path == "tenacity/stop.py":
            target_paths.extend(existing(["tests/test_tenacity.py"]))
            keywords.add("stop")
        elif path == "tenacity/retry.py":
            target_paths.extend(existing(["tests/test_tenacity.py"]))
            keywords.add("retry")
        elif path in {"tenacity/after.py", "tenacity/before.py", "tenacity/before_sleep.py"}:
            target_paths.extend(existing(["tests/test_tenacity.py"]))
            keywords.update(["log", "before", "after"])
        elif path.startswith("tenacity/"):
            target_paths.extend(existing(["tests/test_tenacity.py"]))
    targets: list[str] = []
    for item in target_paths:
        if item not in targets:
            targets.append(item)
    if targets and keywords:
        targets.extend(["-k", " or ".join(sorted(keywords))])
    if not targets:
        targets.extend(existing(["tests"]))
    deduped: list[str] = []
    for item in targets:
        if item not in deduped:
            deduped.append(item)
    return deduped


def main() -> int:
    explicit = [arg for arg in sys.argv[1:] if arg]
    targets = explicit or targets_from_changes(changed_files())
    if not targets:
        print("No pytest targets found; expected a tests/ directory.", file=sys.stderr)
        return 2
    cmd = ["python3", "-m", "pytest", "-q", *targets]
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
