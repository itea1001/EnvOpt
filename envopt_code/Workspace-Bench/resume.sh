#!/usr/bin/env bash
# Runs INSIDE the box to RESUME a timed-out session: --resume once, then auto-continue
# the SAME session until /work/REPORT.md exists (or too many tries / the outer timeout).
cd /work
claude --resume "$WB_SID" -p "RESUME: your previous session was stopped by a time limit, not finished. Keep working in THIS turn — there are NO notifications/wakeups, so never wait for one; poll any target run you start in a foreground loop until it is done. Only stop once you have written /work/REPORT.md." ${EVOLVE_MODEL:+--model "$EVOLVE_MODEL"} --dangerously-skip-permissions || true

tries=0
while [ ! -f /work/REPORT.md ]; do
  tries=$((tries + 1))
  [ "$tries" -gt 100 ] && { echo "[resume] gave up after $tries continues without REPORT.md"; break; }
  echo "[resume #$tries] no /work/REPORT.md yet — continuing the same session"
  sleep 5
  claude --continue -p "You were just restarted. Keep working in THIS turn, no waiting for notifications. Finish and write /work/REPORT.md." ${EVOLVE_MODEL:+--model "$EVOLVE_MODEL"} --dangerously-skip-permissions || true
done
echo "[resume] done (REPORT.md: $([ -f /work/REPORT.md ] && echo yes || echo no), continues: $tries)"
