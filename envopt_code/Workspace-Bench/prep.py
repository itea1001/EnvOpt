#!/usr/bin/env python3
"""Build a runnable all-worlds Workspace-Bench eval-root for one Lite evolve step.

We use ONLY Lite tasks, and a step's tasks span all 5 worlds, so a step's access layer holds
ALL 5 worlds. Each launch gets its OWN timestamped dir <EVOLVE>/evolve/step<N>_<timestamp>/
(real copies, no symlinks):

  seed     : <stepdir>/access/<world>/ = a real copy the agent edits, for every world
             step 1   = a copy of each bare world (filesys/<world>_raw)
             step n>1 = a copy of the LATEST step<n-1>_* dir's access (the previous product)
  stage    : copy this step's Lite task slice into <stepdir>/tasks/, stripping rubrics
  assemble : build <stepdir>/run/ = the eval-root; each filesys/<world>_raw is an empty
             mountpoint the docker run RO-mounts the matching access/<world> over.

No inject step. Lite tasks already carry their data in the world, so training and held-out are
structurally identical -- no `_task_inputs`, no train/test mismatch.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from config import WB_EVAL, WORLDS, EVOLVE_ROOT

STRIP_KEYS = ("rubrics", "rubric_types")   # judge-only; hidden from the evolve agent
STEPS = EVOLVE_ROOT / "evolve"             # all-world Lite runs live here as step<N>_<timestamp>


def _latest_prev(n: int) -> Path:
    """The most recent evolve/step<n-1>_* dir (to build step n on)."""
    cands = sorted(STEPS.glob(f"step{n-1}_*"))
    if not cands:
        raise SystemExit(f"no previous step found: looked for {STEPS}/step{n-1}_* (run step {n-1} first)")
    return cands[-1]


def seed(n: int, stepdir, from_access=None) -> Path:
    """<stepdir>/access/<world>/ = a real copy for every world. Step 1 from the bare worlds;
    step n>1 MUST be given from_access = the prev step's access dir (no guessing). Symlinks preserved."""
    access = Path(stepdir) / "access"
    if access.exists():
        sys.stderr.write(f"WARNING: reusing existing {access} — NOT re-seeded.\n")
        return access
    if n <= 1:
        src_for = lambda w: WB_EVAL / "filesys" / f"{w}_raw"
    else:
        if not from_access:
            raise SystemExit(f"step {n} requires --from <prev step's access dir>; refusing to guess.")
        base = Path(from_access)
        if not base.is_dir():
            raise SystemExit(f"--from dir not found: {base}")
        sys.stderr.write(f"  seeding step {n} from {base}\n")
        src_for = lambda w: base / w
    access.mkdir(parents=True)
    for w in WORLDS:
        src = src_for(w)
        if not src.exists():
            raise SystemExit(f"cannot seed: source {src} missing")
        shutil.copytree(src, access / w, symlinks=True)
    return access


def stage(stepdir, ids: list) -> Path:
    """Copy the step's Lite task dirs into <stepdir>/tasks/, stripping rubrics (answers)."""
    tdir = Path(stepdir) / "tasks"
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    for tid in ids:
        src = WB_EVAL / "tasks_lite" / tid
        if not src.is_dir():
            raise SystemExit(f"lite task not found: {src}")
        dst = tdir / tid
        shutil.copytree(src, dst)
        mp = dst / "metadata.json"
        d = json.loads(mp.read_text(encoding="utf-8"))
        for k in STRIP_KEYS:
            d.pop(k, None)
        mp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return tdir


def assemble(stepdir, with_sdk: bool = False) -> Path:
    """Build <stepdir>/run/ = an eval-root for all worlds; filesys/<world>_raw are empty
    mountpoints the docker run RO-mounts each access/<world> over (see wb-compose.yaml)."""
    sd = Path(stepdir)
    access = sd / "access"
    tasks = sd / "tasks"
    if not access.exists():
        raise SystemExit(f"missing access: {access} (seed first)")
    if not tasks.exists():
        raise SystemExit(f"missing tasks: {tasks} (stage first)")
    run = sd / "run"
    if run.exists():
        shutil.rmtree(run)
    run.mkdir(parents=True)
    dirs = ["scripts", "src", "runs", "docker"]
    if with_sdk:
        # ClaudeCode ONLY. Its harness runs baselines/ClaudeCode.js, which imports
        # evaluation/node_modules/@anthropic-ai/claude-agent-sdk (189 MB). Codex never touches
        # either — the codex CLI is installed in the image — so this stays off by default and
        # a codex eval-root keeps exactly the 4 dirs it has always had.
        dirs += ["baselines", "node_modules"]
    for d in dirs:
        shutil.copytree(WB_EVAL / d, run / d, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(tasks, run / "tasks")
    fz = run / "filesys"
    fz.mkdir()
    for w in WORLDS:
        (fz / f"{w}_raw").mkdir()   # empty mountpoint; docker run RO-mounts access/<world> here
    (run / "output").mkdir()
    return run


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("seed");     p.add_argument("step", type=int); p.add_argument("stepdir"); p.add_argument("--from", dest="from_access", default=None)
    p = sub.add_parser("stage");    p.add_argument("stepdir"); p.add_argument("ids", help="comma-separated lite task ids")
    p = sub.add_parser("assemble"); p.add_argument("stepdir")
    p.add_argument("--with-sdk", action="store_true", help="also copy baselines/ + node_modules/ (ClaudeCode harness only)")
    a = ap.parse_args()
    if a.cmd == "seed":
        print(seed(a.step, a.stepdir, a.from_access))
    elif a.cmd == "stage":
        print(stage(a.stepdir, [t.strip() for t in a.ids.split(",") if t.strip()]))
    elif a.cmd == "assemble":
        print(assemble(a.stepdir, a.with_sdk))
