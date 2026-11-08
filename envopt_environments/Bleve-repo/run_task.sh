#!/usr/bin/env bash
# Run one Bleve task with a given environment layer, the way our experiments did.
#
# Usage: ./run_task.sh <instance_id> [layer_dir] [--strip-tests]
#   instance_id    a SWE-smith Bleve task, e.g. blevesearch__bleve.f2876b5e.lm_modify__0380uwjg
#   layer_dir      e.g. step_5/layer; omit for the baseline (no layer)
#   --strip-tests  delete *_test.go before the agent starts (evolve runs did this;
#                  our held-out val/test runs kept the tests)
#
# Needs: docker, python3 with the `datasets` package, ANTHROPIC_API_KEY,
#        and a Claude Code binary (set CLAUDE_BIN, default: `command -v claude`).
set -euo pipefail

ID=""; LAYER=""; STRIP=0
for a in "$@"; do
  case "$a" in
    --strip-tests) STRIP=1 ;;
    *) if [ -z "$ID" ]; then ID=$a; else LAYER=$(cd "$a" && pwd); fi ;;
  esac
done
[ -n "$ID" ] || { echo "usage: $0 <instance_id> [layer_dir] [--strip-tests]" >&2; exit 2; }

IMAGE=jyangballin/swesmith.x86_64.blevesearch_1776_bleve.f2876b5e
MODEL=claude-haiku-4-5-20251001
CLAUDE_BIN=${CLAUDE_BIN:-$(command -v claude)}
OUT=$(mktemp -d)

# 1. the task's bug patch and bug report, from the SWE-smith dataset
python3 - "$ID" "$OUT" <<'PY'
import sys, datasets
iid, out = sys.argv[1], sys.argv[2]
rows = datasets.load_dataset("SWE-bench/SWE-smith", split="train").filter(lambda r: r["instance_id"] == iid)
open(f"{out}/bug.patch", "w").write(rows[0]["patch"])
open(f"{out}/problem.txt", "w").write(rows[0]["problem_statement"])
PY

# 2. a fresh container with the Bleve repo at /testbed
CID=$(docker run -d --rm -e ANTHROPIC_API_KEY -e IS_SANDBOX=1 \
  -v "$CLAUDE_BIN":/usr/local/bin/claude:ro -v "$OUT":/task:ro "$IMAGE" sleep infinity)
trap 'docker rm -f "$CID" >/dev/null' EXIT

# 3. apply the bug, optionally strip tests, commit as the base
STRIP_CMD=""; [ "$STRIP" = 1 ] && STRIP_CMD="find . -name '*_test.go' -delete &&"
BASE=$(docker exec "$CID" bash -c "cd /testbed && git checkout -qf main && git checkout -qB work && \
  git apply /task/bug.patch && $STRIP_CMD git add -A && \
  git -c user.email=e@e -c user.name=e commit -qm base && git rev-parse HEAD")

# 4. copy the environment layer on top of the repo (untracked files)
[ -n "$LAYER" ] && tar -C "$LAYER" -cf - . | docker exec -i "$CID" tar --no-same-owner -C /testbed -xf -

# 5. run the fixed agent on the bug report
docker exec -i "$CID" bash -c "cd /testbed && timeout 900 claude -p --model $MODEL \
  --output-format stream-json --verbose --dangerously-skip-permissions" \
  < "$OUT/problem.txt" > "$OUT/trajectory.jsonl" || true

# 6. the agent's fix: source-only diff against the base (layer files are untracked, so excluded)
docker exec "$CID" bash -c "cd /testbed && git diff $BASE -- '*.go' ':(exclude)*_test.go'" > "$OUT/fix.diff"

echo "trajectory: $OUT/trajectory.jsonl"
echo "fix:        $OUT/fix.diff"
