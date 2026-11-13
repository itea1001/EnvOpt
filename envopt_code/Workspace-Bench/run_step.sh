#!/usr/bin/env bash
# Launch ONE evolve step.
#
# Step N gets PER_STEP synthetic training tasks (the N-th slice of synth_order.txt) and a copy of
# the environment: the original Workspace-Bench workspaces for step 1, the previous step's
# environment (--from) for later steps. The evolve agent (Claude Code) runs headless in a
# container and launches target runs (Codex + GPT-5.4-mini) through the docker socket.
#
# Usage: run_step.sh --step 1 [--per-step 20] [--budget 100] [--timeout 21600]
#                    [--from <prev step's access dir>] [--dry-run]
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/settings.sh"
EVOLVE=$HERE

STEP=""; PER_STEP=20; BUDGET=100; TIMEOUT=21600; DRYRUN=0; FROM=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --step) STEP="$2"; shift 2;;
    --per-step) PER_STEP="$2"; shift 2;;
    --budget) BUDGET="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --from) FROM="$2"; shift 2;;
    --dry-run) DRYRUN=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
ORDER=$EVOLVE/synth_order.txt; TASKDIR=$EVOLVE/synthetic_tasks
[ -n "$STEP" ] || { echo "need --step" >&2; exit 2; }
[ "$STEP" -ge 1 ] 2>/dev/null || { echo "--step must be >= 1" >&2; exit 2; }
if [ "$STEP" -ge 2 ]; then
  [ -n "$FROM" ] || { echo "FATAL: step >= 2 requires --from <prev step's access dir>" >&2; exit 2; }
  [ -d "$FROM" ] || { echo "FATAL: --from dir not found: $FROM" >&2; exit 2; }
fi

TS=$(date +%s)
STEPDIR=$EVOLVE/evolve/step${STEP}_${TS}

echo "=== preflight ==="
if [ -n "$ANTHROPIC_API_KEY" ]; then echo "  evolve agent: ANTHROPIC_API_KEY"
else [ -f "$CLAUDE_CREDS" ] || { echo "FATAL: no ANTHROPIC_API_KEY and no Claude login at $CLAUDE_CREDS"; exit 1; }
     echo "  evolve agent: Claude login at $CLAUDE_CREDS"; fi
if [ -n "$GPT54MINI_API_KEY" ]; then echo "  target agent: GPT54MINI_API_KEY"
else [ -f "$CODEX_HOME_HOST/auth.json" ] || { echo "FATAL: no GPT54MINI_API_KEY and no Codex login at $CODEX_HOME_HOST/auth.json"; exit 1; }
     echo "  target agent: Codex login at $CODEX_HOME_HOST"; fi
mkdir -p "$CODEX_HOME_HOST"
[ -S "$DOCKER_SOCK" ] || { echo "FATAL: no docker socket at $DOCKER_SOCK"; exit 1; }
docker image inspect workspace-bench:local >/dev/null 2>&1 || { echo "FATAL: build workspace-bench:local first (see README)"; exit 1; }
docker image inspect wb-evolve-box:local   >/dev/null 2>&1 || { echo "FATAL: build wb-evolve-box:local first (see README)"; exit 1; }
echo "  ok"

# ── this step's slice: PER_STEP ids from the frozen synthetic order ──────────
FIRST=$(( (STEP - 1) * PER_STEP ))
SLICE=$(python3 -c "
ids=open('$ORDER').read().strip().split(',')
s=ids[$FIRST:$FIRST+$PER_STEP]
assert s, 'step $STEP is past the end of the pool'
print(','.join(s))")
echo "=== step $STEP slice ($(echo "$SLICE" | tr ',' '\n' | grep -c .) tasks) ==="
echo "  $SLICE"

echo "=== prepare: seed access + stage tasks + assemble eval-root ==="
mkdir -p "$STEPDIR"
python3 "$EVOLVE/prep.py" seed "$STEP" "$STEPDIR" ${FROM:+--from "$FROM"} >/dev/null
mkdir -p "$STEPDIR/tasks"
for t in $(echo "$SLICE" | tr ',' ' '); do
  [ -d "$TASKDIR/$t" ] || { echo "FATAL: missing $TASKDIR/$t"; exit 1; }
  cp -r "$TASKDIR/$t" "$STEPDIR/tasks/$t"
done
python3 "$EVOLVE/prep.py" assemble "$STEPDIR" >/dev/null
cp "$EVOLVE/docker/wb-compose.yaml" "$STEPDIR/wb-compose.yaml"
cp "$EVOLVE/boxrun.sh" "$STEPDIR/boxrun.sh"
mkdir -p "$STEPDIR/evolve_log/claude"
sed "s/{{BUDGET}}/$BUDGET/" "$EVOLVE/EVOLVE_BRIEF.md" > "$STEPDIR/BRIEF.md"
echo "  step dir ready: $STEPDIR"
echo "  staged: $(ls "$STEPDIR/tasks" | wc -l) tasks"

if [ "$DRYRUN" = "1" ]; then
  echo "=== dry-run: setup complete, NOT launching the agent ==="
  ls -la "$STEPDIR"; exit 0
fi

# Claude auth for the evolve agent: API key, or the subscription login file.
CLAUDE_AUTH=(-e ANTHROPIC_API_KEY)
[ -n "$ANTHROPIC_API_KEY" ] || CLAUDE_AUTH=(-v "$CLAUDE_CREDS":/root/.claude/.credentials.json)

echo "=== launch the evolve agent (Claude Code), headless ==="
docker run --rm \
  -v "$DOCKER_SOCK":"$DOCKER_SOCK" \
  "${CLAUDE_AUTH[@]}" \
  -v "$STEPDIR/evolve_log/claude":/root/.claude/projects \
  -e DOCKER_HOST="unix://$DOCKER_SOCK" \
  -e CLAUDE_CONFIG_DIR=/root/.claude \
  -e IS_SANDBOX=1 \
  -e EVOLVE_MODEL \
  -e GPT54MINI_API_KEY -e GPT54MINI_BASE_URL -e CODEX_HOME_HOST \
  -e WB_RUN_DIR="$STEPDIR/run" \
  -e WB_ACCESS_DIR="$STEPDIR/access" \
  -e COMPOSE_PROJECT_NAME="wb_step${STEP}_${TS}" \
  -v "$STEPDIR":/work \
  -w /work \
  wb-evolve-box:local \
  bash -c "cd /work && timeout $TIMEOUT bash /work/boxrun.sh" 2>&1 | tee "$STEPDIR/evolve_log/session.log"

echo "=== step $STEP done ==="
echo "  environment:  $STEPDIR/access"
echo "  report:       $STEPDIR/REPORT.md"
echo "  next step:    run_step.sh --step $((STEP+1)) --from $STEPDIR/access"
echo "  validate:     run_val.sh --access $STEPDIR/access --name step${STEP}"
