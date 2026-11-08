#!/usr/bin/env bash
set -euo pipefail

files=("$@")
if [ "${#files[@]}" -eq 0 ]; then
  mapfile -t files < <(git diff --name-only -- '*.go' ':(exclude)*_test.go')
fi

if [ "${#files[@]}" -eq 0 ]; then
  echo "no changed non-test Go files to validate" >&2
  exit 1
fi

declare -A dirs=()
for f in "${files[@]}"; do
  [[ "$f" == *.go && "$f" != *_test.go ]] || continue
  d=$(dirname "$f")
  [[ "$d" == "." ]] && d="."
  dirs["$d"]=1
done

if [ "${#dirs[@]}" -eq 0 ]; then
  echo "no changed non-test Go packages to validate" >&2
  exit 1
fi

status=0
for d in $(printf '%s\n' "${!dirs[@]}" | sort); do
  if [[ "$d" == "." ]]; then
    pkg="."
  else
    pkg="./$d"
  fi
  echo "==> go test $pkg"
  if ! go test "$pkg"; then
    status=1
  fi
done

exit "$status"
