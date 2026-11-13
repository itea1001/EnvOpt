#!/usr/bin/env bash
# Judge an already-completed val target run.
#
# Why this exists: agent_as_a_judge reads metadata.json from EACH CASE's output dir
# (src/agent_as_a_judge.py:293-299), not from the tasks_lite mount. run_val.sh stages the
# rubric-STRIPPED metadata for the target, so the case dirs have no rubrics and the judge
# exits immediately. This merges rubrics back into the case metadata (after the target has
# already run, so the answering model never saw them), then runs the judge.
#
# Usage: judge_val.sh <val dir>          e.g. val/baseline_<timestamp>
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/settings.sh"
MAIN_REPO=$WB_REPO
EV=/workspace/Workspace-Bench/evaluation
# Same judge as run_val.sh. Empty key => subscription mode (Claude login in CLAUDE_CREDS).
JUDGE_MODEL=claude-sonnet-5
JUDGE_BASE_URL=
JUDGE_API_KEY=$ANTHROPIC_API_KEY
JUDGE_WORKERS=10

VALDIR="${1:?usage: judge_val.sh <val dir>}"; VALDIR="${VALDIR%/}"
[ -d "$VALDIR/judge_tasks" ] || { echo "FATAL: no judge_tasks in $VALDIR"; exit 1; }
OUTRUN=$(ls "$VALDIR/run/output" | head -1)
[ -n "$OUTRUN" ] || { echo "FATAL: no run under $VALDIR/run/output"; exit 1; }
echo "=== judging $OUTRUN ==="

python3 - "$VALDIR" "$OUTRUN" <<'PY'
import json,os,sys
vd,run=sys.argv[1],sys.argv[2]
base=os.path.join(vd,'run','output',run)
n=miss=0
for t in sorted(os.listdir(base)):
    cm=os.path.join(base,t,'metadata.json')
    src=os.path.join(vd,'judge_tasks',t,'metadata.json')
    if not (os.path.isfile(cm) and os.path.isfile(src)): continue
    d=json.load(open(cm,encoding='utf-8')); s=json.load(open(src,encoding='utf-8'))
    if not s.get('rubrics'): miss+=1; continue
    d['rubrics']=s['rubrics']; d['rubric_types']=s.get('rubric_types')
    json.dump(d,open(cm,'w',encoding='utf-8'),ensure_ascii=False,indent=2); n+=1
print(f"  rubrics merged into {n} case dirs" + (f" ({miss} source tasks had none)" if miss else ""))
PY

JUDGE_CREDS=()
[ -n "$JUDGE_API_KEY" ] || JUDGE_CREDS=(-v "$CLAUDE_CREDS":/root/.claude/.credentials.json:ro)
docker run --rm --network host -w "$EV" \
  -e JUDGE_API_KEY="$JUDGE_API_KEY" -e JUDGE_BASE_URL="$JUDGE_BASE_URL" -e JUDGE_MODEL="$JUDGE_MODEL" \
  -e CLAUDE_CONFIG_DIR=/root/.claude -e IS_SANDBOX=1 \
  -e WORKSPACE_BENCH_ROOT=/workspace/Workspace-Bench -e WORKSPACE_BENCH_EVAL_ROOT="$EV" \
  -v "$MAIN_REPO":/workspace/Workspace-Bench \
  -v "$VALDIR/judge_tasks":"$EV/tasks_lite":ro \
  -v "$VALDIR/run/output":"$EV/output" \
  "${JUDGE_CREDS[@]}" \
  workspace-bench:local \
  python3 -u "$EV/src/agent_as_a_judge.py" \
    --task-dir "$EV/output/$OUTRUN" --eval-yaml runs/judge.yaml \
    --overwrite --parallel --workers "$JUDGE_WORKERS" 2>&1 | tee "$VALDIR/judge.log"

echo "=== score ==="
python3 - "$VALDIR/run/output/$OUTRUN" "$JUDGE_MODEL" <<'PY'
import json,glob,os,sys
base,jm=sys.argv[1],sys.argv[2]
p=t=0; rows=[]
for f in sorted(glob.glob(os.path.join(base,'*',f'rubrics_judge--{jm}.json'))):
    s=json.load(open(f,encoding='utf-8')).get('summary',{})
    tid=os.path.basename(os.path.dirname(f)); a,b=s.get('passed',0),s.get('total',0)
    rows.append((tid,a,b)); p+=a; t+=b
for tid,a,b in rows: print(f"  task {tid:<7} {a}/{b}")
print(f"\nVAL SCORE: {p}/{t} rubrics = {p/t*100:.1f}%  over {len(rows)} tasks" if t else "\nNO JUDGE OUTPUT")
PY
