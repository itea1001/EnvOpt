#!/usr/bin/env bash
# Grade an access layer on the 20-task VALIDATION split (originals, with rubrics).
#
# Two passes, as the benchmark does them:
#   1) target run  — codex + gpt-5.4-mini on val_20 through the given access layer
#   2) judge pass  — Claude Code + claude-sonnet-5 checks each task's rubrics against the produced files
#
# The judge reads rubrics from tasks_lite inside the container, so the val tasks are
# mounted there. The target's own copy under run/tasks has rubrics STRIPPED, so the
# answering model never sees them.
#
# Usage: run_val.sh --access <step's access dir> --name <label> [--tasks <ids file>] [--target-only]
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/settings.sh"
EVOLVE=$HERE
MAIN_REPO=$WB_REPO
EV=/workspace/Workspace-Bench/evaluation
LITE=$MAIN_REPO/evaluation/tasks_lite

# Judge: Claude Code with claude-sonnet-5. With an empty key it uses the Claude login in
# CLAUDE_CREDS (subscription mode, see workspace-bench.patch).
JUDGE_MODEL=claude-sonnet-5
JUDGE_BASE_URL=
JUDGE_API_KEY=$ANTHROPIC_API_KEY
JUDGE_WORKERS=10   # per saved project convention: --workers 10 for ALL judge commands

ACCESS=""; NAME=""; TASKS=$EVOLVE/val_20.txt; TARGET_ONLY=0
# Target model. These defaults reproduce every result measured so far — do not change them.
# The codex version is part of the harness, so a different image is a different experiment.
MODEL=gpt-5.4-mini; MODEL_NAME=GPT-5.4-mini; ENV_PREFIX=GPT54MINI; IMAGE=workspace-bench:local
HARNESS=Codex
while [ "$#" -gt 0 ]; do
  case "$1" in
    --access) ACCESS="$2"; shift 2;;
    --name) NAME="$2"; shift 2;;
    --tasks) TASKS="$2"; shift 2;;
    --target-only) TARGET_ONLY=1; shift;;
    --model) MODEL="$2"; shift 2;;
    --model-name) MODEL_NAME="$2"; shift 2;;
    --env-prefix) ENV_PREFIX="$2"; shift 2;;
    --image) IMAGE="$2"; shift 2;;
    --harness) HARNESS="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
# Everything below branches on HARNESS. With the default (Codex) every branch takes the same
# path it always has: same compose template, same 4-dir eval-root, no CLAUDE.md, no extra mounts.
case "$HARNESS" in
  Codex)      COMPOSE=$EVOLVE/docker/wb-compose.yaml;    SDK_FLAG="";           CLAUDE_MD=0;;
  ClaudeCode) COMPOSE=$EVOLVE/docker/wb-compose-cc.yaml; SDK_FLAG="--with-sdk"; CLAUDE_MD=1;;
  *) echo "FATAL: --harness must be Codex or ClaudeCode (got: $HARNESS)" >&2; exit 2;;
esac
# gpt-5.6-* is rejected by codex 0.130.0 (the pinned image); it needs >= 0.144.
case "$MODEL" in
  gpt-5.6-*) [ "$IMAGE" != "workspace-bench:local" ] || {
      echo "FATAL: $MODEL needs codex >= 0.144 — add: --image workspace-bench:codex149" >&2; exit 2; };;
esac
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "FATAL: image not found: $IMAGE" >&2; exit 1; }
[ -n "$ACCESS" ] || { echo "need --access <access dir>" >&2; exit 2; }
[ -d "$ACCESS" ] || { echo "FATAL: access dir not found: $ACCESS" >&2; exit 2; }
[ -n "$NAME" ]   || { echo "need --name <label>" >&2; exit 2; }
[ -f "$TASKS" ]  || { echo "FATAL: task id file not found: $TASKS" >&2; exit 2; }

TS=$(date +%s)
VALDIR=$EVOLVE/val/${NAME}_${TS}
RUN="val_${NAME}"
IDS=$(tr ',' ' ' < "$TASKS" | tr -s ' ')
N=$(echo "$IDS" | wc -w)
echo "=== val: $N tasks | access=$ACCESS | run=$RUN ==="

mkdir -p "$VALDIR"
cp -r "$ACCESS" "$VALDIR/access"
# target copy: rubrics stripped.  judge copy: rubrics intact.
mkdir -p "$VALDIR/tasks" "$VALDIR/judge_tasks"
for t in $IDS; do
  [ -d "$LITE/$t" ] || { echo "FATAL: lite task not found: $LITE/$t"; exit 1; }
  cp -r "$LITE/$t" "$VALDIR/judge_tasks/$t"
  cp -r "$LITE/$t" "$VALDIR/tasks/$t"
  python3 - "$VALDIR/tasks/$t/metadata.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p,encoding='utf-8'))
for k in ('rubrics','rubric_types'): d.pop(k,None)
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
PY
done
# Claude Code auto-loads CLAUDE.md, never AGENTS.md (its bundled cli.js mentions AGENTS.md only
# inside the /init prompt). Our layers put the guide in AGENTS.md, so without this the guide is
# invisible and we would only be measuring the .text/ twins. Same bytes, second filename — and
# written into THIS RUN'S COPY of the access layer, never the source layer on disk.
if [ "$CLAUDE_MD" = "1" ]; then
  n=0
  for w in chanpin kaifa research yunying houqin; do
    if [ -f "$VALDIR/access/$w/AGENTS.md" ]; then
      cp "$VALDIR/access/$w/AGENTS.md" "$VALDIR/access/$w/CLAUDE.md"; n=$((n+1))
    fi
  done
  echo "  ClaudeCode: mirrored AGENTS.md -> CLAUDE.md in $n/5 worlds (this run's copy only)"
fi
python3 "$EVOLVE/prep.py" assemble "$VALDIR" $SDK_FLAG >/dev/null
cp "$COMPOSE" "$VALDIR/wb-compose.yaml"
echo "  staged $(ls "$VALDIR/tasks" | wc -l) tasks (rubrics stripped for the target)"

echo "=== pass 1: target run ($HARNESS + $MODEL, image $IMAGE) ==="
cd "$VALDIR"
WB_IMAGE="$IMAGE" WB_RUN_DIR="$VALDIR/run" WB_ACCESS_DIR="$VALDIR/access" \
docker compose -f wb-compose.yaml run --rm workspace-bench bash -lc "
set -e
CFG=\$(python scripts/build_run_config.py --harness $HARNESS --model $MODEL \
        --model-name $MODEL_NAME --env-prefix $ENV_PREFIX --dataset full \
        --run-name $RUN --timeout-sec 2000)
python scripts/prepare_workdirs_for_run.py --run-config \"\$CFG\"
python src/agent_runner.py --run-config \"\$CFG\"
" 2>&1 | tee "$VALDIR/target.log"

OUTRUN="$HARNESS--$MODEL_NAME--$RUN"
[ -d "$VALDIR/run/output/$OUTRUN" ] || { echo "FATAL: no target output at $VALDIR/run/output/$OUTRUN"; exit 1; }

if [ "$TARGET_ONLY" = "1" ]; then
  echo "=== --target-only: skipping judge ==="; echo "output: $VALDIR/run/output/$OUTRUN"; exit 0
fi

echo "=== pass 2: judge ($JUDGE_MODEL, workers $JUDGE_WORKERS) ==="
# The judge reads metadata.json from each CASE dir (agent_as_a_judge.py:293-299), and those
# copies have rubrics stripped for the target. Merge rubrics back in now that the target has
# already run — it never saw them.
python3 - "$VALDIR" "$OUTRUN" <<'PY'
import json,os,sys
vd,run=sys.argv[1],sys.argv[2]
base=os.path.join(vd,'run','output',run); n=0
for t in sorted(os.listdir(base)):
    cm=os.path.join(base,t,'metadata.json'); src=os.path.join(vd,'judge_tasks',t,'metadata.json')
    if not (os.path.isfile(cm) and os.path.isfile(src)): continue
    d=json.load(open(cm,encoding='utf-8')); s=json.load(open(src,encoding='utf-8'))
    if not s.get('rubrics'): continue
    d['rubrics']=s['rubrics']; d['rubric_types']=s.get('rubric_types')
    json.dump(d,open(cm,'w',encoding='utf-8'),ensure_ascii=False,indent=2); n+=1
print(f"  rubrics merged into {n} case dirs")
PY
JUDGE_CREDS=()
[ -n "$JUDGE_API_KEY" ] || JUDGE_CREDS=(-v "$CLAUDE_CREDS":/root/.claude/.credentials.json:ro)
docker run --rm --network host -w "$EV" \
  -e JUDGE_API_KEY="$JUDGE_API_KEY" \
  -e JUDGE_BASE_URL="$JUDGE_BASE_URL" \
  -e JUDGE_MODEL="$JUDGE_MODEL" \
  -e CLAUDE_CONFIG_DIR=/root/.claude \
  -e IS_SANDBOX=1 \
  -e WORKSPACE_BENCH_ROOT=/workspace/Workspace-Bench \
  -e WORKSPACE_BENCH_EVAL_ROOT="$EV" \
  -v "$MAIN_REPO":/workspace/Workspace-Bench \
  -v "$VALDIR/judge_tasks":"$EV/tasks_lite":ro \
  -v "$VALDIR/run/output":"$EV/output" \
  "${JUDGE_CREDS[@]}" \
  workspace-bench:local \
  python3 -u "$EV/src/agent_as_a_judge.py" \
    --task-dir "$EV/output/$OUTRUN" \
    --eval-yaml runs/judge.yaml \
    --overwrite --parallel --workers "$JUDGE_WORKERS" 2>&1 | tee "$VALDIR/judge.log"

echo "=== val summary ==="
python3 - "$VALDIR/run/output/$OUTRUN" "$JUDGE_MODEL" <<'PY'
import json,glob,os,sys
base,jm=sys.argv[1],sys.argv[2]
tot=passed=0; rows=[]
for f in sorted(glob.glob(os.path.join(base,'*',f'rubrics_judge--{jm}.json'))):
    s=json.load(open(f,encoding='utf-8')).get('summary',{})
    t=os.path.basename(os.path.dirname(f))
    p,n=s.get('passed',0),s.get('total',0)
    rows.append((t,p,n)); passed+=p; tot+=n
for t,p,n in rows: print(f'  task {t:<6} {p}/{n} rubrics')
print(f'\nVAL SCORE: {passed}/{tot} rubrics = {passed/tot*100:.1f}%  over {len(rows)} tasks' if tot else '\nNO JUDGE OUTPUT FOUND')
PY
echo "val dir: $VALDIR"
