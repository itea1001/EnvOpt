# Tenacity-repo

Environments from our evolve run on Tenacity bug-fixing tasks (SWE-smith, `jd/tenacity`) — the
setting of the Advisor Models paper. The fixed target agent is mini-swe-agent with Gemini 2.5 Flash,
capped at 40 steps.

- `step_1/layer/` … `step_5/layer/`: the environment layer the evolve agent built at each step.
  Each step starts from the previous step's layer, so later steps contain the earlier files.
  Step 4 is our final environment; step 5 was rejected.
- `baseline/layer/`: empty. The baseline agent works on the plain repo with no layer.
  (`.gitkeep` only keeps the empty folder in git.)
- `run_task.sh`: runs one task with a given layer.

## The Tenacity repo is not included

Each task builds its own copy of the repo, so we ship only the layers. For every task:

1. Start from the SWE-smith image `jyangballin/swesmith.x86_64.jd_1776_tenacity.0d40e76f`
   (repo at `/testbed`). The task's bug already sits on a branch named after the task.
2. Check out that branch, then replace the git history with a single commit, so no earlier commit
   or other branch holds the fix.
3. Copy the layer into the repo root.
4. Run the agent on the task's bug report, with no network. Its fix is the `git diff` of tracked
   files against that commit (layer files are untracked, so they are never part of the fix).

As in SWE-smith, the tests that catch each bug are removed from the branch, so the agent works
without them.

## How the layer reaches the agent

mini-swe-agent loads no instruction file on its own — there is no equivalent of Claude Code's
`CLAUDE.md` or Codex's `AGENTS.md`. So the runner reads `/testbed/AGENTS.md` and adds it to the
conversation directly after the system prompt. Without this the agent rarely opens the notes and
the layer has little effect. Baseline runs have no `AGENTS.md`, so nothing is added.

The agent is the Advisor Models paper's own copy of mini-swe-agent (`az1326/advisor-models` at
commit `f27efa7`), driven the way their `agent_server.py` drives it: their `default.yaml` prompt,
Gemini's default temperature, and the empty `<advice>` block their no-advisor baseline also carries.

## Tasks

All tasks are in `SWE-bench/SWE-smith-py` on Hugging Face. Train (56) and test (49) are the
Advisor Models splits — `data/swe_smith/train_jd__tenacity.json` and
`data/swe_smith/validation_jd__tenacity.json` in their repo (the second is their test set).
Our val split is the other 44 Tenacity tasks that have a bug report.
