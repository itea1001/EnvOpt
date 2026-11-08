Tenacity repair notes
=====================

Best first command: `python3 .agent_tools/tenacity_triage.py 'important symbols from issue'`.
Use symbols and nouns, for example `retry_all retry_any`, `wait_exponential wait_incrementing`, `AsyncRetrying retry_if_result`, `after_log`, `RetryCallState seconds_since_start`, or `stop_after_attempt stop_any`.

Command format reminder: every reply needs exactly one fenced bash command. Put no Python examples or Markdown code fences in your reasoning. If several shell operations belong together, chain them in that one command with `&&`.

Fast workflow:
1. Run `tenacity_triage.py` with issue symbols.
2. Inspect only the small source ranges it points to.
3. Make the minimal implementation edit. If several adjacent lines in one file are wrong, edit them together in one command and inspect `git diff` rather than re-reading after every line.
4. Prefer the built-in finite smoke checks over ad hoc repro files: run `python3 .agent_tools/validate_tenacity.py` after source edits, or `python3 .agent_tools/tenacity_semantics.py async|wait|stop|retry|engine|state|copy|all` for a narrower check.
5. If validation passes and `git diff` is minimal, submit with `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`.

Do not edit tests unless the issue explicitly says the tests are the product bug. If a test command fails during collection, inspect the collection error and switch to a narrower test or finite reproduction before changing test files.
Put throwaway reproductions at the repository root or use `python3 -c`; avoid creating ad hoc files under `tests/` because pytest may collect them.

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
- This checkout has no `tests/test_tenacity.py`; do not spend commands looking for it.
- Existing pytest files are `tests/test_asyncio.py`, `tests/test_tornado.py`, `tests/test_after.py`, `tests/test_issue_478.py`, and `tests/test_utils.py`.
- `tests/test_after.py` imports a missing helper module in this benchmark checkout, so logging callback changes are usually faster to validate with a direct reproduction.
- Async behavior: `tests/test_asyncio.py`.
- Tornado behavior: `tests/test_tornado.py`.

General Tenacity semantics:
- `RetryCallState.attempt_number` is 1-based.
- `RetryCallState` constructor shape is `RetryCallState(retry_object, fn, args, kwargs)`.
- State reset methods should restore every state field to the class default shown next to the field declaration; fixing only the first attribute that crashes often leaves later retry bookkeeping corrupted.
- `seconds_since_start` is based on the stored outcome timestamp minus `start_time`; it should be `None` before an outcome exists, not recomputed from live wall-clock time.
- In `BaseRetrying.copy`, `_first_set(new_value, existing_value)` keeps the caller-provided override when it is not `None`; copied constructor fields should consistently pass the requested keyword first and the current attribute second.
- Bug-report snippets sometimes use a short or stale `RetryCallState(...)` call shape. For wait/stop/retry predicate checks, a `types.SimpleNamespace(...)` with just the needed fields is usually faster and less brittle.
- There is no useful global `tenacity.retry_state`; observe retry state through callbacks (`before`, `after`, `before_sleep`) or by directly constructing a state object.
- `Future.construct(attempt_number, value, has_exception)` builds stored outcomes for direct predicate tests.
- `retry_any` and `stop_any` are OR combinators; `retry_all` and `stop_all` are AND combinators.
- Wait bounds clamp the computed delay to configured limits after the strategy computes the raw delay.
- Python `sum(wait_strategies)` starts with integer `0`; reverse addition for wait strategies should respect that neutral element.
- Logging callbacks should preserve the requested log level, callback/function name, and configured formatting.
- Async predicates may be sync callables, coroutine functions, or async predicate objects; use the existing `_utils.wrap_to_async_func` pattern when a maybe-sync callable must be awaited.
- `AsyncRetrying` takes normal constructor keywords such as `stop=tenacity.stop_after_attempt(1)`. In `async for attempt in AsyncRetrying(...)`, `attempt` is an `AttemptManager`; use `attempt.retry_state.attempt_number` for the attempt number.

Validation safety:
- For wait strategies, direct-call the wait object with a tiny state object that has `attempt_number`; a full retry loop is usually unnecessary.
- If a shell search or replacement contains `*`, `+`, `(`, or `)`, prefer inspecting the exact line and using a line-number edit or a quoted literal replacement; unescaped regex metacharacters often make `sed` do nothing.
- For stop strategies, direct-call the stop object with a tiny state object that has `attempt_number` and/or `seconds_since_start`; `types.SimpleNamespace(...)` is enough and avoids read-only `RetryCallState` properties.
- For decorators, `async def`, classes, or multi-line callbacks, use a heredoc file or `python3 - <<'PY' ... PY`; one-line `python3 -c` commonly breaks on decorators and async definitions.
- For strategy classes, edit the concrete class named by the issue rather than abstract base methods or placeholder `pass` methods unless the traceback points there.
- Do not validate `stop_after_delay` or `stop_any(stop_after_delay(...), ...)` by racing wall-clock time against `stop_after_attempt` in a retry loop. Use direct state calls unless the bug is specifically about real sleeping or scheduling.
- If a decorated retry reproduction is useful, always include a small independent safety stop such as `stop_after_attempt(3)` and use `wait_none()` or `wait_fixed(0)` so a broken policy finishes quickly.
- For `stop_never`, validate by direct-calling `stop_never(state)` or combine it with `stop_any(stop_never, stop_after_attempt(3))`; never run a bare `stop=stop_never` decorated function.
- `validate_tenacity.py` knows this benchmark's missing broad test file and runs finite semantic smoke checks for changed Tenacity modules before focused pytest files. It exits nonzero on any failed smoke check or pytest failure.
