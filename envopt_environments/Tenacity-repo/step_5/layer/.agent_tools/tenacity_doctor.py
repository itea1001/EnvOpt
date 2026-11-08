#!/usr/bin/env python3
"""Static Tenacity source checks with grouped repair signals.

The checks inspect the current checkout only. They are meant to make common
retry-engine damage obvious in one command, especially after an edit leaves a
class half-repaired.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path.cwd()
INIT = ROOT / "tenacity" / "__init__.py"
TORNADO = ROOT / "tenacity" / "tornadoweb.py"


def parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        print(f"{path.relative_to(ROOT)}:{exc.lineno}: syntax error: {exc.msg}")
        print("Fix syntax before behavioral validation; inspect the edited block and restore its full signature/body.")
        return None


def class_named(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def function_named(node: ast.AST, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for child in getattr(node, "body", []):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
            return child
    return None


def assigned_self_attrs(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    assigned: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                assigned.add(target.attr)
    return assigned


def check_base_constructor(tree: ast.Module) -> list[str]:
    problems: list[str] = []
    base = class_named(tree, "BaseRetrying")
    init = function_named(base, "__init__") if base else None
    if not isinstance(init, ast.FunctionDef):
        return ["BaseRetrying.__init__ was not found; inspect tenacity/__init__.py around class BaseRetrying."]
    expected = [
        "sleep",
        "stop",
        "wait",
        "retry",
        "before",
        "after",
        "before_sleep",
        "reraise",
        "retry_error_cls",
        "retry_error_callback",
    ]
    assigned = assigned_self_attrs(init)
    missing = [name for name in expected if name not in assigned]
    if missing:
        problems.append(
            "BaseRetrying.__init__ is missing self assignments for: "
            + ", ".join(missing)
            + ". Restore all missing constructor attributes together before revalidating."
        )
    return problems


class NameUseVisitor(ast.NodeVisitor):
    def __init__(self, target: str) -> None:
        self.target = target
        self.first_load: int | None = None
        self.first_store: int | None = None

    def visit_Name(self, node: ast.Name) -> None:
        if node.id != self.target:
            return
        if isinstance(node.ctx, ast.Load) and self.first_load is None:
            self.first_load = node.lineno
        if isinstance(node.ctx, ast.Store) and self.first_store is None:
            self.first_store = node.lineno


def check_sleep_flow(tree: ast.Module) -> list[str]:
    problems: list[str] = []
    base = class_named(tree, "BaseRetrying")
    post_stop = function_named(base, "_post_stop_check_actions") if base else None
    next_action = function_named(post_stop, "next_action") if post_stop else None
    if not next_action:
        return problems
    visitor = NameUseVisitor("sleep")
    visitor.visit(next_action)
    if visitor.first_load and (visitor.first_store is None or visitor.first_load < visitor.first_store):
        problems.append(
            "BaseRetrying._post_stop_check_actions.next_action uses sleep before assigning it; keep the retry sleep flow as upcoming_sleep -> RetryAction.sleep -> statistics."
        )
    return problems


def check_iter_shape(tree: ast.Module) -> list[str]:
    problems: list[str] = []
    base = class_named(tree, "BaseRetrying")
    iter_fn = function_named(base, "__iter__") if base else None
    if not iter_fn:
        return problems
    source = ast.get_source_segment(INIT.read_text(), iter_fn) or ""
    if "self.iter_state" in source:
        problems.append(
            "BaseRetrying.__iter__ is using self.iter_state as retry call state. IterState is internal action bookkeeping; __iter__ should use one local RetryCallState for iter(), AttemptManager, and prepare_for_next_attempt()."
        )
    if ".retry_state" in source:
        problems.append(
            "BaseRetrying has no self.retry_state property in this checkout; __iter__ should keep a local RetryCallState variable."
        )
    if ".result" in source:
        problems.append(
            "BaseRetrying.__iter__ should not unwrap do.result in the final branch; self.iter() returns the final action/value and raises retry errors itself."
        )
    retry_state_lines: list[int] = []
    begin_lines: list[int] = []
    while_lines: list[int] = []
    for node in ast.walk(iter_fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "retry_state":
                    retry_state_lines.append(node.lineno)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "begin":
                begin_lines.append(node.lineno)
        elif isinstance(node, ast.While):
            while_lines.append(node.lineno)
    if while_lines:
        first_loop = min(while_lines)
        if not begin_lines or min(begin_lines) > first_loop:
            problems.append("BaseRetrying.__iter__ should call begin() before entering the retry loop.")
        if not retry_state_lines or min(retry_state_lines) > first_loop:
            problems.append(
                "BaseRetrying.__iter__ should create the RetryCallState before the retry loop and pass that same state through iter(), AttemptManager, and prepare_for_next_attempt()."
            )
    call_fn = function_named(base, "__call__") if base else None
    if isinstance(call_fn, ast.FunctionDef):
        has_abstractmethod = any(
            isinstance(item, ast.Name) and item.id == "abstractmethod"
            for item in call_fn.decorator_list
        )
        if not has_abstractmethod:
            problems.append("BaseRetrying.__call__ should remain decorated with @abstractmethod.")
    return problems


def check_tornado_shape(tree: ast.Module) -> list[str]:
    problems: list[str] = []
    klass = class_named(tree, "TornadoRetrying")
    call_fn = function_named(klass, "__call__") if klass else None
    if not call_fn:
        return problems
    source = ast.get_source_segment(TORNADO.read_text(), call_fn) or ""
    if "RetryCallState" not in source:
        problems.append("TornadoRetrying.__call__ should build a RetryCallState for its retry loop.")
    if "gen.Return" not in source:
        problems.append("TornadoRetrying.__call__ should return final non-sleep/non-attempt outcomes through gen.Return.")
    if ".sleep_amount" in source:
        problems.append("DoSleep is a float subclass in this checkout; pass it directly to self.sleep(do), not do.sleep_amount.")
    return problems


def main() -> int:
    problems: list[str] = []
    init_tree = parse(INIT)
    if init_tree is not None:
        problems.extend(check_base_constructor(init_tree))
        problems.extend(check_sleep_flow(init_tree))
        problems.extend(check_iter_shape(init_tree))
    if TORNADO.exists():
        tornado_tree = parse(TORNADO)
        if tornado_tree is not None:
            problems.extend(check_tornado_shape(tornado_tree))
    if problems:
        print("Tenacity source doctor found structural issues:")
        for problem in problems:
            print("- " + problem)
        return 1
    print("ok tenacity source doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
