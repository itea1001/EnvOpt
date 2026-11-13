#!/usr/bin/env python3
"""Shared config for workspace-bench-evolve.

Everything we create lives under EVOLVE_ROOT. The benchmark repo (WB_*) is a
read-only source of code + original worlds + tasks; we never write to it.
"""
import os
from pathlib import Path

# Read-only benchmark source.
WB_REPO = Path(os.environ["WB_REPO"])  # set by settings.sh
WB_EVAL = WB_REPO / "evaluation"

# Our project root (the only place we write).
EVOLVE_ROOT = Path(__file__).resolve().parent

# world key (filesys folder prefix) -> task metadata "file_system" value
# (exact mapping from evaluation/scripts/build_run_config.py ROLE_DIRS)
WORLD_TO_FS = {
    "chanpin":  "产品人员",        # Product
    "kaifa":    "开发人员",        # Backend
    "research": "研究人员",        # Researcher
    "yunying":  "运营人员",        # Operations
    "houqin":   "行政/后勤人员",   # Logistics
}
WORLDS = list(WORLD_TO_FS)

# friendly names -> world key
ALIASES = {
    "operations": "yunying", "ops": "yunying", "yunying": "yunying",
    "logistics": "houqin", "houqin": "houqin",
    "researcher": "research", "research": "research",
    "backend": "kaifa", "kaifa": "kaifa",
    "product": "chanpin", "chanpin": "chanpin",
}

# WB code subfolders symlinked into a run eval-root. NOT tasks/tasks_lite/filesys.
CODE_DIRS = ["scripts", "src", "docker", "baselines", "deepagents", "runs"]


def world_key(name: str) -> str:
    k = ALIASES.get(str(name).strip().lower())
    if not k:
        raise SystemExit(f"unknown world: {name!r} (known: {', '.join(WORLDS)})")
    return k


def world_dir(world: str) -> Path:
    return EVOLVE_ROOT / world
