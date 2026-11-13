#!/usr/bin/env bash
# Resume an evolve step that was stopped by its time limit before it wrote REPORT.md.
# Relaunches the evolve container with `claude --resume <session>` and keeps it going until
# /work/REPORT.md exists or the timeout is reached.
#
# Usage: resume_step.sh <stepdir> [timeout_seconds]     (default timeout 21600 = 6 h)
set -euo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/settings.sh"
EVOLVE=$HERE

STEPDIR="${1:?usage: resume_step.sh <stepdir> [timeout_seconds]}"
TIMEOUT="${2:-21600}"
STEPDIR="${STEPDIR%/}"
BASE=$(basename "$STEPDIR")
[ -d "$STEPDIR/access" ] || { echo "FATAL: no access at $STEPDIR/access"; exit 1; }
[ -f "$STEPDIR/REPORT.md" ] && { echo "REPORT.md already exists — nothing to resume."; exit 0; }
JSONL=$(ls -t "$STEPDIR"/evolve_log/claude/*/*.jsonl 2>/dev/null | head -1)
[ -n "$JSONL" ] || { echo "FATAL: no session jsonl under $STEPDIR/evolve_log/claude"; exit 1; }
SID=$(basename "$JSONL" .jsonl)
echo "=== resume $STEPDIR  session=$SID  timeout=${TIMEOUT}s ==="

if [ -z "$ANTHROPIC_API_KEY" ]; then
  [ -f "$CLAUDE_CREDS" ] || { echo "FATAL: no ANTHROPIC_API_KEY and no Claude login at $CLAUDE_CREDS"; exit 1; }
fi
[ -S "$DOCKER_SOCK" ] || { echo "FATAL: no docker socket at $DOCKER_SOCK"; exit 1; }
docker image inspect wb-evolve-box:local >/dev/null 2>&1 || { echo "FATAL: build wb-evolve-box:local first"; exit 1; }

cp "$EVOLVE/resume.sh" "$STEPDIR/resume.sh"

CLAUDE_AUTH=(-e ANTHROPIC_API_KEY)
[ -n "$ANTHROPIC_API_KEY" ] || CLAUDE_AUTH=(-v "$CLAUDE_CREDS":/root/.claude/.credentials.json)

docker run --rm \
  -v "$DOCKER_SOCK":"$DOCKER_SOCK" \
  "${CLAUDE_AUTH[@]}" \
  -v "$STEPDIR/evolve_log/claude":/root/.claude/projects \
  -e DOCKER_HOST="unix://$DOCKER_SOCK" \
  -e CLAUDE_CONFIG_DIR=/root/.claude \
  -e IS_SANDBOX=1 \
  -e WB_SID="$SID" \
  -e EVOLVE_MODEL \
  -e GPT54MINI_API_KEY -e GPT54MINI_BASE_URL -e CODEX_HOME_HOST \
  -e WB_RUN_DIR="$STEPDIR/run" \
  -e WB_ACCESS_DIR="$STEPDIR/access" \
  -e COMPOSE_PROJECT_NAME="wb_${BASE}_resume" \
  -v "$STEPDIR":/work \
  -w /work \
  wb-evolve-box:local \
  bash -c "cd /work && timeout $TIMEOUT bash /work/resume.sh" 2>&1 | tee "$STEPDIR/evolve_log/resume_session.log"

echo "=== resume ended; REPORT.md present: $([ -f "$STEPDIR/REPORT.md" ] && echo yes || echo no); environment at $STEPDIR/access ==="
