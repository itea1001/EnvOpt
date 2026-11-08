#!/usr/bin/env bash
set -euo pipefail

test_file="analysis/lang/pl/stempel/zz_agent_trie_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package stempel

import "testing"

func TestAgentTrieGetLastOnPathSmoke(t *testing.T) {
	tr := &trie{
		cmds:    []string{"A", "B"},
		root:    0,
		forward: true,
		rows: []*row{
			{cells: map[rune]*cell{'a': {cmd: 0, ref: 1}}},
			{cells: map[rune]*cell{'b': {cmd: 1, ref: -1}}},
		},
	}
	got := string(tr.GetLastOnPath([]rune("ab")))
	if got != "B" {
		t.Fatalf("GetLastOnPath(ab)=%q want B", got)
	}
}
GO

go test ./analysis/lang/pl/stempel -run TestAgentTrieGetLastOnPathSmoke -count=1
