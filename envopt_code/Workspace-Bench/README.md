# EnvOpt on Workspace-Bench

Code to run EnvOpt's environment evolution on Workspace-Bench, as used in the paper.
The research (evolve) agent is Claude Code. The fixed target agent is Codex with GPT-5.4-mini.
Each step gives the evolve agent 20 synthetic training tasks without verifiers.
The environments our run produced are described in `../../envopt_environments/Workspace-Bench/`.

## What is here

| File | What it does |
|---|---|
| `run_step.sh` | Runs one evolve step. |
| `resume_step.sh` | Resumes a step that hit its time limit before it wrote `REPORT.md`. |
| `run_val.sh` | Runs the target agent on the validation or test tasks and grades the results. |
| `judge_val.sh` | Grades a finished `run_val.sh` target run again. |
| `EVOLVE_BRIEF.md` | The prompt the evolve agent receives (`{{BUDGET}}` is filled in by `run_step.sh`). |
| `boxrun.sh`, `resume.sh` | Run Claude Code inside the evolve container and restart it if it stops early. |
| `prep.py`, `config.py` | Copy the environment and build the folder the target agent runs in. |
| `synthetic_tasks/`, `synth_order.txt` | The 200 synthetic training tasks, and the order in which steps use them. |
| `val_20.txt`, `test_80.txt` | The Workspace-Bench Lite task ids we used for validation and test. |
| `docker/` | The evolve container (`Dockerfile`) and the target-agent run setup (`wb-compose.yaml`). |
| `workspace-bench.patch` | Our changes to Workspace-Bench (see below). |
| `settings.sh`, `settings.example.sh` | Paths and logins. |

## Setup

1. **Workspace-Bench.** Clone it at the commit our patch was made against, apply the patch,
   and download the workspaces and Lite tasks:

   ```
   git clone https://github.com/OpenDataBox/Workspace-Bench.git
   cd Workspace-Bench
   git checkout 4bf11e4e627187077b96e6738112692bd8f7ee6d
   git apply /path/to/envopt_code/Workspace-Bench/workspace-bench.patch
   cd evaluation && python3 scripts/download_hf_assets.py --lite --workspaces
   ```

   The patch lets Codex, Claude Code and the judge run with a subscription login when no API key
   is set, retries transient API errors, records cache tokens for Claude Code, and runs the judge
   in parallel.

2. **Docker images.**

   ```
   docker compose -f Workspace-Bench/evaluation/docker/docker-compose.yaml build   # workspace-bench:local
   docker build -t wb-evolve-box:local envopt_code/Workspace-Bench/docker          # evolve container
   ```

3. **Settings.** Copy `settings.example.sh` to `settings.local.sh` and fill it in:
   - `WB_REPO`: your Workspace-Bench checkout.
   - Claude (evolve agent and judge): `ANTHROPIC_API_KEY`, or leave it empty to use a Claude
     subscription login at `CLAUDE_CREDS`.
   - Codex (target agent): `GPT54MINI_API_KEY` and `GPT54MINI_BASE_URL`, or leave the key empty
     to use a ChatGPT subscription login in `CODEX_HOME_HOST`.

   The evolve container starts target runs through the host's docker socket, so it must be able
   to use docker on the host.

## Running

```
./run_step.sh --step 1                                    # step 1 starts from the original workspaces
./run_val.sh --access evolve/step1_<ts>/access --name step1
./run_step.sh --step 2 --from evolve/step1_<ts>/access    # each step starts from the previous one
./run_val.sh --access evolve/step2_<ts>/access --name step2
...
```

- Each step writes to `evolve/step<N>_<timestamp>/`. The new environment is in `access/`,
  the agent's report in `REPORT.md`, and its full transcript in `evolve_log/`.
- Defaults: 20 tasks per step (`--per-step`), a target-agent budget of $100 per step (`--budget`),
  and a 6-hour limit (`--timeout`). `--dry-run` prepares a step without starting the agent.
- `run_val.sh` uses the 20 validation tasks by default. Add `--tasks test_80.txt` for the test set.
  It writes to `val/<name>_<timestamp>/` and prints the rubric score. Stop when the validation
  cost goes up or accuracy drops, and keep the previous step.
- Each step copies all five workspaces, about 24 GB per step.
