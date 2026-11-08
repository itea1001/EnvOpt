#!/usr/bin/env bash
set -euo pipefail

files=("$@")
if [ "${#files[@]}" -eq 0 ]; then
  mapfile -t files < <(git diff --name-only -- '*.go' ':(exclude)*_test.go')
fi

if [ "${#files[@]}" -eq 0 ]; then
  echo "no changed non-test Go files"
  exit 0
fi

declare -A dirs=()
for f in "${files[@]}"; do
  [[ "$f" == *.go && "$f" != *_test.go ]] || continue
  d=$(dirname "$f")
  [[ "$d" == "." ]] && d="."
  dirs["$d"]=1
done

for d in "${!dirs[@]}"; do
  echo "go test ./$d"
  if [[ "$d" == "." ]]; then
    go test .
  else
    go test "./$d"
  fi
done
