# Copy to settings.local.sh and fill in. settings.local.sh is git-ignored.

# Workspace-Bench checkout with workspace-bench.patch applied and the workspaces downloaded.
WB_REPO=/path/to/Workspace-Bench

# Claude (evolve agent + judge): an API key, or leave empty to use a subscription login.
ANTHROPIC_API_KEY=
CLAUDE_CREDS=$HOME/.claude/.credentials.json
EVOLVE_MODEL=

# Codex target agent: an API key, or leave empty to use a ChatGPT subscription login.
GPT54MINI_API_KEY=
GPT54MINI_BASE_URL=https://api.openai.com/v1
CODEX_HOME_HOST=$HOME/.codex

# Docker socket (detected automatically if empty).
DOCKER_SOCK=
