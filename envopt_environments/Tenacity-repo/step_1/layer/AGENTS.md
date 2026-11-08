Tenacity repair notes
=====================

First useful command: run `python3 .agent_tools/tenacity_triage.py 'important symbols from issue'`.
Use symbols and nouns, for example `retry_all retry_any`, `wait_exponential wait_incrementing`, `AsyncRetrying retry_if_result`, `after_log`, or `stop_after_attempt stop_any`.

Command format reminder: every reply needs exactly one fenced bash command. Put no Python examples or Markdown code fences in your reasoning. If you need several shell operations, chain them in that one command with `&&`.

Fast workflow:
1. Use `tenacity_triage.py` with issue symbols.
2. Inspect only the small source ranges it points to.
3. Edit the minimal implementation. For multi-line edits, prefer an exact string replacement or a carefully scoped range after viewing the snippet.
4. Run a focused pytest or finite reproduction. Avoid unbounded retry repros.
5. Run `python3 .agent_tools/validate_tenacity.py` when tests are available, then submit with `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.

Do not edit tests unless the issue explicitly says the tests are the product bug. If a test command fails during collection, inspect the collection error and switch to a narrower test or finite reproduction before changing test files.

Source map:
- `tenacity/__init__.py`: retry engines and state: `retry`, `Retrying`, `BaseRetrying`, `RetryCallState`, `Future`, `RetryError`, `TryAgain`, `DoAttempt`, `DoSleep`.
- `tenacity/retry.py`: retry predicates and combinators. Retry predicates return `True` to retry.
- `tenacity/stop.py`: stop policies and combinators. Stop predicates return `True` to stop.
- `tenacity/wait.py`: wait strategies and additive composition. Wait callables receive `RetryCallState` and return seconds.
- `tenacity/after.py`, `before.py`, `before_sleep.py`: callback/logging helpers.
- `tenacity/asyncio/__init__.py`: async retry engine. `tenacity/asyncio/retry.py`: async retry predicates.
- `tenacity/_utils.py`: callback names, seconds conversion, ordinal formatting, async wrapping.
- `tenacity/tornadoweb.py`: Tornado integration. `tenacity/nap.py`: sleep helpers.

Test map:
- Most sync behavior: `tests/test_tenacity.py`.
- Async behavior: `tests/test_asyncio.py`.
- Tornado behavior: `tests/test_tornado.py`.

General Tenacity semantics:
- `RetryCallState.attempt_number` is 1-based.
- `RetryCallState` constructor shape is `RetryCallState(retry_object, fn, args, kwargs)`.
- `Future.construct(attempt_number, value, has_exception)` builds stored outcomes for direct predicate tests.
- `retry_any` and `stop_any` are OR combinators; `retry_all` and `stop_all` are AND combinators.
- Wait bounds clamp the computed delay to configured limits after the strategy computes the raw delay.
- Python `sum(wait_strategies)` starts with integer `0`; reverse addition for wait strategies should respect that neutral element.
- Logging callbacks should preserve the requested log level, callback/function name, and configured formatting.
- Async predicates may be sync callables, coroutine functions, or async predicate objects; use the existing `_utils.wrap_to_async_func` pattern when a maybe-sync callable must be awaited.

Validation safety:
- For wait strategies, direct-call the wait object with a tiny state object that has `attempt_number`; a full retry loop is usually unnecessary.
- For stop strategies, direct-call the stop object with a tiny state object that has `attempt_number` and/or `seconds_since_start`; this avoids accidental infinite retry loops.
- If a decorated retry reproduction is useful, always include a small independent safety stop such as `stop_after_attempt(3)` and use `wait_none()` or `wait_fixed(0)` so a broken policy finishes quickly.
