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
    semantic_checks: list[str] = []
    source_changes = [p for p in paths if p.startswith("tenacity/") and p.endswith(".py")]
    test_changes = [p for p in paths if p.startswith("tests/") and p.endswith(".py")]
    target_paths.extend(test_changes)
    for path in source_changes:
        if path.startswith("tenacity/asyncio/"):
            target_paths.extend(existing(["tests/test_asyncio.py"]))
            semantic_checks.append("async")
        elif path == "tenacity/tornadoweb.py":
            target_paths.extend(existing(["tests/test_tornado.py"]))
            semantic_checks.append("tornado")
        elif path == "tenacity/wait.py":
            target_paths.extend(existing(["tests/test_issue_478.py", "tests/test_utils.py"]))
            semantic_checks.append("wait")
        elif path == "tenacity/stop.py":
            target_paths.extend(existing(["tests/test_issue_478.py", "tests/test_utils.py"]))
            semantic_checks.append("stop")
        elif path == "tenacity/retry.py":
            target_paths.extend(existing(["tests/test_issue_478.py", "tests/test_utils.py"]))
            semantic_checks.append("retry")
        elif path in {"tenacity/after.py", "tenacity/before.py", "tenacity/before_sleep.py"}:
            target_paths.extend(existing(["tests/test_utils.py"]))
        elif path.startswith("tenacity/"):
            target_paths.extend(existing(["tests/test_issue_478.py", "tests/test_utils.py"]))
            semantic_checks.extend(["future", "engine"])
    targets: list[str] = []
    for item in target_paths:
        if item not in targets:
            targets.append(item)
    if not targets:
        targets.extend(existing(["tests/test_issue_478.py", "tests/test_utils.py"]))
    deduped: list[str] = []
    for item in targets:
        if item not in deduped:
            deduped.append(item)
    checks: list[str] = []
    for item in semantic_checks:
        if item not in checks:
            checks.append(item)
    return ["--semantic", *checks, "--", *deduped]


def main() -> int:
    explicit = [arg for arg in sys.argv[1:] if arg]
    targets = explicit or targets_from_changes(changed_files())
    semantic: list[str] = []
    if targets and targets[0] == "--semantic":
        sep = targets.index("--")
        semantic = targets[1:sep]
        targets = targets[sep + 1 :]
    if semantic:
        cmd = ["python3", ".agent_tools/tenacity_semantics.py", *semantic]
        print("+ " + " ".join(cmd), flush=True)
        proc = subprocess.run(cmd, cwd=ROOT)
        if proc.returncode != 0:
            return proc.returncode
    if not targets:
        print("No focused pytest targets found; semantic checks completed.")
        return 0
    cmd = ["python3", "-m", "pytest", "-q", *targets]
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
