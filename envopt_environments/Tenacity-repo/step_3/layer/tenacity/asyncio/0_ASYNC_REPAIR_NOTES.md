Async Tenacity repair notes
===========================

For async-only issues, run:
`python3 .agent_tools/tenacity_triage.py 'AsyncRetrying async predicate symbols'`

Inspect the async engine as a mirror of the synchronous engine: constructor pass-through, `copy`, `__call__`, `iter`, `__aiter__`, `__anext__`, `_run_retry`, `_run_wait`, and `_run_stop`.

Maybe-sync async predicate callables should follow the existing `_utils.wrap_to_async_func` pattern.

Async reproductions should use `async def`, `asyncio.run(...)`, small `stop_after_attempt(...)`, and `wait_none()` or `wait_fixed(0)`.
Use `AsyncRetrying(stop=tenacity.stop_after_attempt(1))` for finite async-iterator checks. The item yielded by `async for` is an `AttemptManager`; read the state as `attempt.retry_state`.

Fast async smoke check after an edit:
`python3 .agent_tools/tenacity_semantics.py async`
