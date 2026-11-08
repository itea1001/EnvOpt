Start here for faster Tenacity repairs
======================================

Read `AGENTS.md` for the full compact notes.

Best first useful command after seeing the issue:
`python3 .agent_tools/tenacity_triage.py 'important symbols from the issue'`

Avoid full-file `cat` when a symbol-specific snippet will do. For wait and stop policies, validate by direct-calling the policy object with a tiny state object when possible; decorated retry loops need a small safety stop and zero wait.
