#!/usr/bin/env bash
# Run one Tenacity task with a given environment layer, the way our experiments did.
#
# Usage: ./run_task.sh <instance_id> [layer_dir]
#   instance_id  a SWE-smith Tenacity task, e.g. jd__tenacity.0d40e76f.combine_file__4gcf36bk
#   layer_dir    e.g. step_4/layer; omit for the baseline (no layer)
#
# Needs: docker, python3 with the `datasets` package, GEMINI_API_KEY, and the Advisor Models
# paper's own copy of mini-swe-agent:
#   pip install "git+https://github.com/az1326/advisor-models.git@f27efa72654a2c5a56a1498f00e558e501bfeba3#subdirectory=advisor_models/swe_smith/mini-swe-agent"
set -euo pipefail

ID=${1:-}; LAYER=""
[ -n "$ID" ] || { echo "usage: $0 <instance_id> [layer_dir]" >&2; exit 2; }
[ -n "${2:-}" ] && LAYER=$(cd "$2" && pwd)

BASE_IMAGE=jyangballin/swesmith.x86_64.jd_1776_tenacity.0d40e76f
LAYER_HASH=""; [ -n "$LAYER" ] && LAYER_HASH=$(tar -C "$LAYER" -cf - . | sha256sum | cut -c1-16)
TAG=tenacity-task-$(printf '%s' "$ID $LAYER_HASH" | sha256sum | cut -c1-16)
OUT=$(mktemp -d)

# 1. the task's bug report, from the SWE-smith dataset
python3 - "$ID" "$OUT" <<'PY'
import sys, datasets
iid, out = sys.argv[1], sys.argv[2]
rows = datasets.load_dataset("SWE-bench/SWE-smith-py", split="train").filter(lambda r: r["instance_id"] == iid)
open(f"{out}/problem.txt", "w").write(rows[0]["problem_statement"])
PY

# 2. an image with the bug checked out, history replaced by one commit, and the layer on top
CTX=${LAYER:-$(mktemp -d)}
{ echo "FROM $BASE_IMAGE"
  echo "RUN cd /testbed && git checkout -qf $ID && git clean -qfd && rm -rf .git && \\"
  echo "    git init -q -b work && git add -A && git -c user.email=e@e -c user.name=e commit -qm base"
  [ -n "$LAYER" ] && echo "COPY . /testbed/"
} | docker build -q -t "$TAG" -f - "$CTX" >/dev/null

# 3. run the fixed agent, as the paper's agent_server.py drives it
python3 - "$TAG" "$OUT" <<'PY'
import json, os, subprocess, sys, yaml, litellm
from minisweagent.agents.default import AgentConfig, DefaultAgent, TerminatingException
from minisweagent.config import get_config_path
from minisweagent.environments.docker import DockerEnvironment
from minisweagent.models.litellm_model import LitellmModel

image, out = sys.argv[1], sys.argv[2]
name = f"tenacity-run-{os.getpid()}"
env = DockerEnvironment(image=image, cwd="/testbed", run_args=["--name", name, "--network=none"])
try:
    a = yaml.safe_load(get_config_path("default.yaml").read_text())["agent"]
    cfg = AgentConfig(system_template=a["system_template"], instance_template=a["instance_template"],
                      action_observation_template=a["action_observation_template"],
                      format_error_template=a["format_error_template"], step_limit=40, cost_limit=3.0)
    agent = DefaultAgent(LitellmModel(model_name="gemini/gemini-2.5-flash"), env,
                         config_class=lambda **kw: cfg)
    start = env.execute("git rev-parse HEAD")["output"].strip()
    u = env.execute("uname -srvm")["output"].split()
    agent.extra_template_vars = {"task": open(f"{out}/problem.txt").read(), "system": u[0],
                                 "release": u[1], "version": u[2], "machine": u[3]}
    agent.messages = []
    agent.add_message("system", agent.render_template(cfg.system_template))
    notes = env.execute("cat /testbed/AGENTS.md 2>/dev/null")["output"].strip()
    if notes:   # mini-swe-agent loads no instruction file itself, so the layer's notes go here
        agent.add_message("user", f"Repository instructions (/testbed/AGENTS.md):\n\n{notes}")
    agent.add_message("user", agent.render_template(cfg.instance_template))
    agent.add_advice("")   # their no-advisor baseline also carries an empty advice block
    status = "MaxSteps"
    for _ in range(40):
        if agent.model.n_calls >= 40:
            break
        try:
            agent.step()
        except TerminatingException as e:
            status = type(e).__name__; break
        except (litellm.exceptions.RateLimitError, litellm.exceptions.AuthenticationError) as e:
            status = type(e).__name__; break
        except Exception as e:   # format errors and command timeouts go back to the model
            agent.add_message("user", str(e)[:300])
    open(f"{out}/fix.diff", "w").write(env.execute(f"git diff {start}")["output"])
    json.dump({"messages": agent.messages, "steps": agent.model.n_calls, "exit_status": status},
              open(f"{out}/trajectory.json", "w"), indent=1, default=str)
    print(f"steps: {agent.model.n_calls}   exit: {status}")
finally:
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
PY

echo "trajectory: $OUT/trajectory.json"
echo "fix:        $OUT/fix.diff"
