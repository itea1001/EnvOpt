#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/validate_changed.sh" "$@"
