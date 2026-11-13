#!/usr/bin/env bash
# Auto-continue wrapper, run INSIDE the box (under an outer `timeout` set by run_step.sh).
#
# The evolve agent keeps trying to "end its turn and wait for a notification / background waiter"
# — which NEVER fires in headless `claude -p`. So we make bailing impossible: if it ends its turn
# before writing /work/REPORT.md, we immediately resume the SAME session and tell it to keep
# going. The loop ends when REPORT.md exists, after too many resumes, or when the outer timeout
# kills it.
cd /work

claude -p "$(cat /work/BRIEF.md)" ${EVOLVE_MODEL:+--model "$EVOLVE_MODEL"} --dangerously-skip-permissions || true

tries=0
while [ ! -f /work/REPORT.md ]; do
  tries=$((tries + 1))
  if [ "$tries" -gt 100 ]; then
    echo "[auto-continue] gave up after $tries resumes without REPORT.md"
    break
  fi
  echo "[auto-continue #$tries] agent ended its turn with no /work/REPORT.md — resuming the same session"
  sleep 5
  claude --continue -p "You were just RESTARTED because you ended your turn. There are NO notifications, background waiters, or wakeups in this environment — they never fire, so never wait for one. Keep working in THIS turn: when you start a target run, poll it yourself in a foreground loop until it is done, and only stop once you have written /work/REPORT.md." ${EVOLVE_MODEL:+--model "$EVOLVE_MODEL"} --dangerously-skip-permissions || true
done

echo "[auto-continue] done (REPORT.md present: $([ -f /work/REPORT.md ] && echo yes || echo no), resumes: $tries)"
