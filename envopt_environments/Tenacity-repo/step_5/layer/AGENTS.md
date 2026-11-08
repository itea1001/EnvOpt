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
- Tornado behavior: `python3 .agent_tools/tenacity_semantics.py tornado` is faster and checks decorator dispatch plus direct `TornadoRetrying`; `tests/test_tornado.py` is the broader pytest target.

General Tenacity semantics:
- `RetryCallState.attempt_number` is 1-based.
- Retry sleep data flows through the engine as `wait(retry_state)` -> `retry_state.upcoming_sleep` -> `RetryAction.sleep` -> `retry_state.next_action.sleep`; `before_sleep_log` only displays that final value.
- `BaseRetrying.iter_state` stores state on `threading.local`; a missing thread-local attribute raises `AttributeError`, and the property should initialize the state before returning it.
- `IterState` is not `RetryCallState`. In `BaseRetrying.__iter__`, use one local `RetryCallState(self, fn=None, args=(), kwargs={})` for `iter()`, `AttemptManager`, and `prepare_for_next_attempt()`; do not pass `self.iter_state` and do not look for `self.retry_state`.
- When editing near `BaseRetrying.__iter__`, preserve the `@abstractmethod` decorator on the following `__call__` method.
- `RetryCallState` constructor shape is `RetryCallState(retry_object, fn, args, kwargs)`.
- State reset methods should restore every state field to the class default shown next to the field declaration; fixing only the first attribute that crashes often leaves later retry bookkeeping corrupted.
- `seconds_since_start` is based on the stored outcome timestamp minus `start_time`; it should be `None` before an outcome exists, not recomputed from live wall-clock time.
- In `BaseRetrying.copy`, `_first_set(new_value, existing_value)` keeps the caller-provided override when it is not `None`; copied constructor fields should consistently pass the requested keyword first and the current attribute second.
- Bug-report snippets sometimes use a short or stale `RetryCallState(...)` call shape. For wait/stop/retry predicate checks, a `types.SimpleNamespace(...)` with just the needed fields is usually faster and less brittle.
- There is no useful global `tenacity.retry_state`; observe retry state through callbacks (`before`, `after`, `before_sleep`) or by directly constructing a state object.
- There is no `RetryCallState.current_state()` API; for exhausted retries, inspect `RetryError.last_attempt` and its `attempt_number`, `exception()`, or `result()`.
- `Future.construct(attempt_number, value, has_exception)` builds stored outcomes for direct predicate tests.
- `retry_any` and `stop_any` are OR combinators; `retry_all` and `stop_all` are AND combinators.
- Wait bounds clamp the computed delay to configured limits after the strategy computes the raw delay.
- Python `sum(wait_strategies)` starts with integer `0`; reverse addition for wait strategies should respect that neutral element.
- Logging callbacks should preserve the requested log level, callback/function name, and configured formatting.
- Async predicates may be sync callables, coroutine functions, or async predicate objects; use the existing `_utils.wrap_to_async_func` pattern when a maybe-sync callable must be awaited.
- `AsyncRetrying` takes normal constructor keywords such as `stop=tenacity.stop_after_attempt(1)`. In `async for attempt in AsyncRetrying(...)`, `attempt` is an `AttemptManager`; use `attempt.retry_state.attempt_number` for the attempt number.
- `TornadoRetrying.__call__` mirrors the sync retry loop but returns final values with `gen.Return`; it should create one `RetryCallState` before the loop, pass `DoSleep` directly to `self.sleep(do)`, and handle the final non-attempt/non-sleep `do`.
- `TornadoRetrying` has no `.call()` helper. For a direct Tornado repro use `tornado.ioloop.IOLoop.current().run_sync(lambda: retrying(fn, *args, **kwargs))`, or just run `python3 .agent_tools/tenacity_semantics.py tornado`.
- The `retry` decorator should choose `AsyncRetrying` for native coroutine functions, `TornadoRetrying` for Tornado coroutine functions, and plain `Retrying` for synchronous functions.
- If validation reports several missing `BaseRetrying.__init__` attributes, fix the constructor assignment block in one edit. Do not add one `self.<name>` line and re-run validation after each attribute.

Validation safety:
- For wait strategies, direct-call the wait object with a tiny state object that has `attempt_number`; a full retry loop is usually unnecessary.
- If a shell search or replacement contains `*`, `+`, `(`, or `)`, prefer inspecting the exact line and using a line-number edit or a quoted literal replacement; unescaped regex metacharacters often make `sed` do nothing.
- For multi-line f-strings, callback log messages, or nested function bodies, avoid complex `sed c\`/`r` quoting. After inspecting line numbers, use `python3 .agent_tools/replace_lines.py path start end <<'EOF' ... EOF` to replace only that small line range. To insert before a line without deleting it, pass `end` as `start - 1`, for example `replace_lines.py file.py 48 47`.
- If an edit damages indentation or leaves duplicate branches, repair the local function/class block with `replace_lines.py`; do not restart with `git reset` or broad file rewrites.
- For stop strategies, direct-call the stop object with a tiny state object that has `attempt_number` and/or `seconds_since_start`; `types.SimpleNamespace(...)` is enough and avoids read-only `RetryCallState` properties.
- For decorators, `async def`, classes, or multi-line callbacks, use a heredoc file or `python3 - <<'PY' ... PY`; one-line `python3 -c` commonly breaks on decorators and async definitions.
- For strategy classes, edit the concrete class named by the issue rather than abstract base methods or placeholder `pass` methods unless the traceback points there.
- Do not validate `stop_after_delay` or `stop_any(stop_after_delay(...), ...)` by racing wall-clock time against `stop_after_attempt` in a retry loop. Use direct state calls unless the bug is specifically about real sleeping or scheduling.
- If a decorated retry reproduction is useful, always include a small independent safety stop such as `stop_after_attempt(3)` and use `wait_none()` or `wait_fixed(0)` so a broken policy finishes quickly.
- For `stop_never`, validate by direct-calling `stop_never(state)` or combine it with `stop_any(stop_never, stop_after_attempt(3))`; never run a bare `stop=stop_never` decorated function.
- `validate_tenacity.py` knows this benchmark's missing broad test file and runs finite semantic smoke checks for changed Tenacity modules before focused pytest files. It exits nonzero on any failed smoke check or pytest failure.
- A passing validation is only current for the source tree at that moment. If you edit source again afterward, re-run validation before submitting.
- `tenacity_doctor.py` is run by `validate_tenacity.py`; when it reports a grouped structural issue, inspect the named method and fix the whole local block before validating again.
