#!/usr/bin/env python3
"""Targeted Tenacity orientation for repair agents.

The script reads the current checkout only. It does not contain fixed source;
it indexes whatever Tenacity tree it is placed into and prints small snippets
around symbols or issue words so an agent can avoid repeated discovery steps.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path.cwd()
SOURCE_DIRS = [ROOT / "tenacity", ROOT / "tests"]
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "but",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "__init__",
    "not",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "tenacity",
    "to",
    "when",
    "with",
}


MODULE_HINTS = [
    ("wait backoff sleep jitter chain increment radd add", ["tenacity/wait.py"]),
    ("stop attempt delay deadline", ["tenacity/stop.py"]),
    ("retry predicate exception result any all unless", ["tenacity/retry.py"]),
    ("engine state error decorator statistics retrycallstate future retryerror", ["tenacity/__init__.py"]),
    ("before callback logging", ["tenacity/before.py"]),
    ("after callback logging log", ["tenacity/after.py"]),
    ("before_sleep callback logging", ["tenacity/before_sleep.py"]),
    ("async await coroutine", ["tenacity/asyncio/__init__.py", "tenacity/asyncio/retry.py"]),
    ("tornado", ["tenacity/tornadoweb.py"]),
    ("utility name seconds ordinal wrap", ["tenacity/_utils.py"]),
]


RELATED_TERMS = {
    "before_sleep_log": ["RetryAction", "BaseAction", "before_sleep", "next_action", "upcoming_sleep"],
    "before_sleep": ["RetryAction", "BaseAction", "next_action", "upcoming_sleep"],
    "after_log": ["RetryCallState", "seconds_since_start", "fn", "attempt_number"],
    "retryerror": ["RetryError", "Future", "last_attempt"],
    "retry_error": ["RetryError", "Future", "last_attempt"],
    "iter_state": ["IterState", "iter_state", "_local"],
}


def py_files() -> list[Path]:
    files: list[Path] = []
    for base in SOURCE_DIRS:
        if base.exists():
            files.extend(sorted(p for p in base.rglob("*.py") if p.is_file()))
    return files


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def tokens(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
    out: list[str] = []
    for tok in raw:
        low = tok.lower()
        if low not in STOP_WORDS and tok not in out:
            out.append(tok)
    return out


def expand_terms(want: list[str]) -> list[str]:
    out = list(want)
    lowered = {w.lower() for w in want}
    for key, extras in RELATED_TERMS.items():
        if key in lowered:
            for extra in extras:
                if extra not in out:
                    out.append(extra)
    return out


def source_index() -> dict[str, list[tuple[Path, int, int, str]]]:
    index: dict[str, list[tuple[Path, int, int, str]]] = {}
    for path in py_files():
        if "tenacity" not in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno)
                index.setdefault(node.name, []).append((path, node.lineno, end, type(node).__name__))
    return index


def likely_modules(
    want: list[str],
    rows: list[tuple[str, Path, int, int, str]] | None = None,
) -> list[Path]:
    selected: list[Path] = []
    exact = {w.lower() for w in want}
    if rows:
        for name, path, _, _, _ in rows:
            if name.lower() in exact and path not in selected:
                selected.append(path)
    if not want:
        for _, paths in MODULE_HINTS:
            for p in paths:
                path = ROOT / p
                if path.exists() and path not in selected:
                    selected.append(path)
                if len(selected) >= 4:
                    return selected
        return selected
    ranked: list[tuple[int, int, Path]] = []
    lowered = [w.lower() for w in want]
    for words, paths in MODULE_HINTS:
        parts = words.split()
        score = 0
        for token in lowered:
            for part in parts:
                if token == part:
                    score += 4
                elif part in token or token in part:
                    score += 2
        if score:
            for p in paths:
                path = ROOT / p
                if path.exists():
                    ranked.append((score, -MODULE_HINTS.index((words, paths)), path))
    for _, _, path in sorted(ranked, reverse=True):
        if path not in selected:
            selected.append(path)
    return selected[:4]


def print_map(want: list[str], rows: list[tuple[str, Path, int, int, str]]) -> None:
    print("== Likely files ==")
    modules = likely_modules(want, rows)
    if modules:
        for path in modules:
            print(f"- {rel(path)}")
    else:
        print("- tenacity/__init__.py")
        print("- tenacity/retry.py")
        print("- tenacity/stop.py")
        print("- tenacity/wait.py")
    print()


def matching_defs(index: dict[str, list[tuple[Path, int, int, str]]], want: list[str]) -> list[tuple[str, Path, int, int, str]]:
    scored: list[tuple[int, int, str, Path, int, int, str]] = []
    lower_want = [w.lower() for w in want]
    for name in sorted(index):
        low_name = name.lower()
        score = 0
        pos = len(lower_want)
        for idx, w in enumerate(lower_want):
            this_score = 0
            if w == low_name:
                this_score = 4
            elif low_name.startswith(w) or w.startswith(low_name):
                this_score = 3
            elif w in low_name or (len(low_name) >= 6 and low_name in w):
                this_score = 2
            if this_score > score or (this_score == score and this_score and idx < pos):
                score = this_score
                pos = idx
        if want and score == 0:
            continue
        for path, start, end, kind in index[name]:
            scored.append((score, pos, name, path, start, end, kind))
    scored.sort(key=lambda row: (row[1], -row[0], row[3].as_posix(), row[4], row[2]))
    return [(name, path, start, end, kind) for _, _, name, path, start, end, kind in scored]


def print_symbol_index(rows: list[tuple[str, Path, int, int, str]]) -> None:
    print("== Matching definitions ==")
    if not rows:
        print("(no direct definition-name matches)")
    for name, path, start, end, kind in rows[:12]:
        print(f"{name}: {rel(path)}:{start}-{end} ({kind})")
    print()


def grep_matches(want: list[str], preferred: list[Path]) -> list[tuple[Path, int, str]]:
    if not want:
        return []
    searchable = [w for w in want if len(w) >= 5 and w.lower() not in {"retry_state", "attempt_number"}]
    if not searchable:
        return []
    pattern = re.compile("|".join(re.escape(w) for w in searchable), re.IGNORECASE)
    matches: list[tuple[Path, int, str]] = []
    files = preferred or py_files()
    test_files = [p for p in py_files() if "tests" in p.parts]
    for path in list(dict.fromkeys([*files, *test_files])):
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            if pattern.search(line):
                matches.append((path, number, line.rstrip()))
    return matches


def print_matches(matches: list[tuple[Path, int, str]]) -> None:
    print("== Short text matches ==")
    if not matches:
        print("(none; use a more specific symbol if needed)")
        print()
        return
    for path, number, line in matches[:12]:
        print(f"{rel(path)}:{number}: {line[:180]}")
    extra = len(matches) - 12
    if extra > 0:
        print(f"... {extra} more matches omitted; narrow the words and rerun.")
    print()


def snippet(path: Path, center: int, radius: int = 8) -> None:
    lines = path.read_text(errors="replace").splitlines()
    start = max(1, center - radius)
    end = min(len(lines), center + radius)
    print(f"--- {rel(path)}:{start}-{end} ---")
    for number in range(start, end + 1):
        print(f"{number:4d}  {lines[number - 1]}")


def print_snippets(rows: list[tuple[str, Path, int, int, str]], matches: list[tuple[Path, int, str]], want: list[str]) -> None:
    print("== Useful snippets ==")
    selected: list[tuple[Path, int]] = []
    seen: set[tuple[Path, int]] = set()
    for _, path, start, _, _ in rows[:4]:
        selected.append((path, start))
        seen.add((path, start))
    for path, number, _ in matches:
        if "tenacity" not in path.parts:
            continue
        key = (path, number)
        if key in seen:
            continue
        seen.add(key)
        selected.append(key)
        if len(selected) >= 4:
            break
    if not selected and want:
        for path in likely_modules(want)[:2]:
                if path.exists():
                    selected.append((path, 1))
    if not selected:
        print("(no snippets selected)")
    definition_keys = {(path, start) for _, path, start, _, _ in rows}
    for path, number in selected:
        snippet(path, number, radius=8 if (path, number) in definition_keys else 4)
    print()


def print_tests(matches: list[tuple[Path, int, str]], want: list[str]) -> None:
    print("== Test targets ==")
    tests = sorted({path for path, _, _ in matches if "tests" in path.parts})
    if tests:
        for path in tests[:6]:
            print(f"- {rel(path)}")
    else:
        print("- no broad tests/test_tenacity.py exists in this checkout")
        print("- tests/test_asyncio.py for async behavior")
        print("- tests/test_tornado.py for Tornado behavior")
        print("- tests/test_utils.py and tests/test_issue_478.py for small existing pytest coverage")
    print()


def print_flow_hints(want: list[str]) -> None:
    low = " ".join(w.lower() for w in want)
    hints: list[str] = []
    if "before_sleep" in low or ("log" in low and "sleep" in low):
        hints.append(
            "before_sleep_log displays retry_state.next_action.sleep; the sync engine fills it as wait(retry_state) -> retry_state.upcoming_sleep -> RetryAction.sleep."
        )
    if "after_log" in low or ("after" in low and "log" in low):
        hints.append(
            "after_log formats retry_state.fn, retry_state.seconds_since_start, retry_state.attempt_number, and retry_state.outcome."
        )
    if "iter_state" in low or "iterstate" in low:
        hints.append(
            "BaseRetrying.iter_state is thread-local; a missing threading.local attribute raises AttributeError, not KeyError, and should be initialized before the property returns."
        )
    if "copy" in low or "retry_with" in low:
        hints.append(
            "BaseRetrying.copy feeds constructor values through _first_set(new_value, existing_value)."
        )
    if not hints:
        return
    print("== Data flow hints ==")
    for hint in hints:
        print("- " + hint)
    print()


def print_validation_hints(want: list[str]) -> None:
    low = " ".join(w.lower() for w in want)
    checks: list[str] = []
    if any(word in low for word in ("async", "await", "coroutine", "aiter", "anext")):
        checks.append("async")
    if any(word in low for word in ("wait", "sleep", "jitter", "backoff", "chain", "combine")):
        checks.append("wait")
    if any(word in low for word in ("stop", "attempt", "delay", "deadline")):
        checks.append("stop")
    if any(word in low for word in ("retry_any", "retry_all", "predicate", "result", "exception")):
        checks.append("retry")
    if any(word in low for word in ("retrycallstate", "seconds_since_start", "prepare_for_next_attempt", "iterstate")):
        checks.append("state")
    if any(word in low for word in ("retry_with", "copy")):
        checks.append("copy")
    if "future" in low:
        checks.append("future")
    deduped: list[str] = []
    for check in checks:
        if check not in deduped:
            deduped.append(check)
    print("== Fast validation ==")
    if deduped:
        print("python3 .agent_tools/tenacity_semantics.py " + " ".join(deduped))
    else:
        print("python3 .agent_tools/validate_tenacity.py")
    print()


def main() -> int:
    query = " ".join(sys.argv[1:])
    want = tokens(query)
    expanded = expand_terms(want)
    index = source_index()
    rows = matching_defs(index, expanded)
    print_map(expanded, rows)
    print(f"Query tokens: {', '.join(want) if want else '(none)'}")
    extras = [w for w in expanded if w not in want]
    if extras:
        print(f"Related terms: {', '.join(extras)}")
    print()
    print_symbol_index(rows)
    preferred = [r[1] for r in rows[:5]] or likely_modules(expanded)
    matches = grep_matches(expanded, preferred)
    print_matches(matches)
    print_snippets(rows, matches, expanded)
    print_flow_hints(expanded)
    print_tests(matches, expanded)
    print_validation_hints(expanded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
