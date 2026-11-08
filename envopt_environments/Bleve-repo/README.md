# Bleve-repo

Environments from our evolve run on Bleve bug-fixing tasks (SWE-smith, `blevesearch/bleve`).
The fixed target agent is Claude Code with Claude Haiku 4.5.

- `step_1/layer/` … `step_6/layer/`: the environment layer the evolve agent built at each step.
  Each step starts from the previous step's layer, so later steps contain the earlier files.
  Step 5 is our final environment; step 6 was rejected.
- `baseline/layer/`: empty. The baseline agent works on the plain repo with no layer.
  (`.gitkeep` only keeps the empty folder in git.)
- `run_task.sh`: runs one task with a given layer.

## The Bleve repo is not included

Each task builds its own copy of the repo, so we ship only the layers. For every task:

1. Start a container from the SWE-smith image
   `jyangballin/swesmith.x86_64.blevesearch_1776_bleve.f2876b5e` (repo at `/testbed`).
2. Apply that task's bug patch from the `SWE-bench/SWE-smith` dataset, and commit the result.
3. Copy the layer into the repo root. Claude Code loads `CLAUDE.md` from there on every turn.
4. Run the agent on the task's bug report. Its fix is the `git diff` of the `.go` source files.

During evolve the `*_test.go` files were deleted before the agent started. In our held-out
val/test runs they were kept (`run_task.sh --strip-tests` switches between the two).
