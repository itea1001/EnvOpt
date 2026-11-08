#!/usr/bin/env python3
"""Cheap semantic smoke checks for Tenacity repairs.

These checks exercise public Tenacity behavior in the current checkout. They
are intentionally small and finite so repair agents can validate common retry,
stop, engine, async, wait, and Tornado changes without creating throwaway test
files or accidentally starting an unbounded retry loop.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
import types
from pathlib import Path


ROOT = Path.cwd()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def tiny_state(**kwargs: object) -> object:
    return types.SimpleNamespace(**kwargs)


def check_future() -> None:
    import tenacity

    fut = tenacity.Future.construct(3, "ok", False)
    check(isinstance(fut, tenacity.Future), "Future.construct must return a Future")
    check(fut.attempt_number == 3, "Future stores attempt_number")
    check(not fut.failed, "Future result must not be marked failed")
    check(fut.result() == "ok", "Future result round-trip")

    exc = ValueError("boom")
    failed = tenacity.Future.construct(4, exc, True)
    check(failed.attempt_number == 4, "exception Future stores attempt_number")
    check(failed.failed, "exception Future must be marked failed")
    check(failed.exception() is exc, "Future exception round-trip")


def check_retry() -> None:
    import tenacity

    retry_state = tiny_state(outcome=tenacity.Future.construct(1, 1, False))
    check(tenacity.retry_if_result(lambda value: value == 1)(retry_state), "retry_if_result retries matching result")
    check(not tenacity.retry_if_result(lambda value: value == 2)(retry_state), "retry_if_result ignores nonmatching result")
    check(tenacity.retry_if_not_result(lambda value: value == 2)(retry_state), "retry_if_not_result retries nonmatching result")
    check(not tenacity.retry_if_not_result(lambda value: value == 1)(retry_state), "retry_if_not_result ignores matching result")

    any_retry = tenacity.retry_any(
        tenacity.retry_never,
        tenacity.retry_if_result(lambda value: value == 1),
    )
    all_retry = tenacity.retry_all(
        tenacity.retry_if_result(lambda value: value == 1),
        tenacity.retry_if_result(lambda value: value < 2),
    )
    check(any_retry(retry_state), "retry_any is an OR combinator")
    check(all_retry(retry_state), "retry_all is an AND combinator")


def check_stop() -> None:
    import tenacity

    state_first = tiny_state(attempt_number=1, seconds_since_start=0.0)
    state_later = tiny_state(attempt_number=3, seconds_since_start=2.0)
    check(not tenacity.stop_never(state_first), "stop_never never stops")
    check(not tenacity.stop_after_attempt(3)(state_first), "stop_after_attempt waits before limit")
    check(tenacity.stop_after_attempt(3)(state_later), "stop_after_attempt stops at limit")
    check(tenacity.stop_after_delay(1)(state_later), "stop_after_delay stops after limit")

    any_stop = tenacity.stop_any(
        tenacity.stop_after_delay(10),
        tenacity.stop_after_attempt(3),
    )
    any_stop_first = tenacity.stop_any(
        tenacity.stop_after_delay(1),
        tenacity.stop_after_attempt(10),
    )
    all_stop = tenacity.stop_all(
        tenacity.stop_after_delay(1),
        tenacity.stop_after_attempt(3),
    )
    check(any_stop(state_later), "stop_any is an OR combinator")
    check(any_stop_first(state_later), "stop_any must consider its first condition")
    check(all_stop(state_later), "stop_all is an AND combinator")
    print("checked stop policies by direct state calls, including stop_any first-condition behavior")


def check_state() -> None:
    import tenacity

    iter_state = tenacity.IterState()
    iter_state.actions.append(lambda retry_state: None)
    iter_state.retry_run_result = True
    iter_state.delay_since_first_attempt = -1
    iter_state.stop_run_result = True
    iter_state.is_explicit_retry = True
    iter_state.reset()
    check(iter_state.actions == [], "IterState.reset restores an empty actions list")
    check(iter_state.retry_run_result is False, "IterState.reset restores retry_run_result default")
    check(iter_state.delay_since_first_attempt == 0, "IterState.reset restores delay_since_first_attempt default")
    check(iter_state.stop_run_result is False, "IterState.reset restores stop_run_result default")
    check(iter_state.is_explicit_retry is False, "IterState.reset restores is_explicit_retry default")

    retrying = tenacity.Retrying(wait=tenacity.wait_none())
    state = tenacity.RetryCallState(retrying, lambda: None, (), {})
    check(state.attempt_number == 1, "RetryCallState starts at attempt 1")
    check(state.seconds_since_start is None, "seconds_since_start is None before an outcome")
    state.set_result("ok")
    elapsed = state.seconds_since_start
    check(elapsed is not None and elapsed >= 0, "seconds_since_start is non-negative after an outcome")
    state.next_action = tenacity.RetryAction(0)
    state.prepare_for_next_attempt()
    check(state.outcome is None, "prepare_for_next_attempt clears outcome")
    check(state.outcome_timestamp is None, "prepare_for_next_attempt clears outcome timestamp")
    check(state.next_action is None, "prepare_for_next_attempt clears next action")
    check(state.attempt_number == 2, "prepare_for_next_attempt increments attempt number")


def check_copy() -> None:
    import tenacity

    def sleeper(seconds: float) -> None:
        pass

    def sleeper2(seconds: float) -> None:
        pass

    def after(retry_state: object) -> None:
        pass

    def before_sleep(retry_state: object) -> None:
        pass

    base = tenacity.Retrying(sleep=sleeper, wait=tenacity.wait_fixed(1), after=after)
    copied = base.copy(sleep=sleeper2, wait=tenacity.wait_fixed(2), before_sleep=before_sleep)
    check(copied.sleep is sleeper2, "copy preserves the provided sleep function")
    check(copied.wait(tiny_state(attempt_number=1)) == 2, "copy preserves the provided wait strategy")
    check(copied.after is after, "copy keeps unchanged callbacks")
    check(copied.before_sleep is before_sleep, "copy preserves the provided before_sleep callback")


def check_wait() -> None:
    import tenacity

    state = tiny_state(attempt_number=3)
    check(tenacity.wait_none()(state) == 0, "wait_none returns zero")
    check(tenacity.wait_fixed(2)(state) == 2, "wait_fixed returns configured delay")
    check((tenacity.wait_fixed(1) + tenacity.wait_fixed(2))(state) == 3, "wait addition sums waits")
    check(sum([tenacity.wait_fixed(1), tenacity.wait_fixed(2)])(state) == 3, "wait reverse-add supports sum")
    bounded = tenacity.wait_exponential(multiplier=10, max=5)
    check(bounded(state) <= 5, "wait_exponential respects max bound")


def check_engine() -> None:
    import tenacity

    raise_once = {"value": True}
    attempts = 0
    for attempt in tenacity.Retrying(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none()):
        with attempt:
            attempts += 1
            if raise_once["value"]:
                raise_once["value"] = False
                raise ValueError("retry me")
    check(attempts == 2, "Retrying context manager retries once then succeeds")

    def always_fails() -> None:
        raise ValueError("fail")

    retrying = tenacity.Retrying(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none())
    try:
        retrying(always_fails)
    except tenacity.RetryError:
        pass
    else:
        raise AssertionError("Retrying should raise RetryError after stop")
    check(retrying.statistics["attempt_number"] == 3, "statistics attempt_number is 1-based final attempt")


async def async_success() -> str:
    return "ok"


def check_async() -> None:
    import tenacity
    import tenacity.asyncio as tenacity_async

    retrying = tenacity_async.AsyncRetrying()
    check(retrying.reraise is False, "AsyncRetrying defaults reraise to False")
    check(retrying.before is tenacity.before_nothing, "AsyncRetrying default before callback")
    check(retrying.after is tenacity.after_nothing, "AsyncRetrying default after callback")
    result = asyncio.run(retrying(async_success))
    check(result == "ok", "AsyncRetrying returns successful coroutine result")

    async def iterate_once() -> int:
        attempts = 0
        async for attempt in tenacity_async.AsyncRetrying(stop=tenacity.stop_after_attempt(1)):
            attempts += 1
            with attempt:
                return attempt.retry_state.attempt_number
        return attempts

    check(asyncio.run(iterate_once()) == 1, "AsyncRetrying is an async iterator that yields attempts")


def check_tornado() -> None:
    import tenacity.tornadoweb as tornadoweb

    calls: list[float] = []
    retrying = tornadoweb.TornadoRetrying(sleep=lambda duration: calls.append(duration))
    retrying.sleep(2.5)
    check(calls == [2.5], "TornadoRetrying.sleep forwards the requested duration unchanged")


CHECKS = {
    "future": check_future,
    "retry": check_retry,
    "stop": check_stop,
    "state": check_state,
    "copy": check_copy,
    "wait": check_wait,
    "engine": check_engine,
    "async": check_async,
    "tornado": check_tornado,
}

ALIASES = {
    "all": tuple(CHECKS),
    "sync": ("future", "retry", "stop", "state", "copy", "wait", "engine"),
}


def expand(names: list[str]) -> list[str]:
    if not names:
        names = ["sync"]
    out: list[str] = []
    for name in names:
        for item in ALIASES.get(name, (name,)):
            if item not in CHECKS:
                raise SystemExit(f"unknown check {item!r}; choices: {', '.join(sorted([*CHECKS, *ALIASES]))}")
            if item not in out:
                out.append(item)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checks", nargs="*", help="checks to run: all, sync, future, retry, stop, wait, engine, async, tornado")
    args = parser.parse_args()
    selected = expand(args.checks)
    for name in selected:
        CHECKS[name]()
        print(f"ok {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
