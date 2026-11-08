#!/usr/bin/env bash
set -euo pipefail

test_file="search/searcher/zz_agent_phrase_paths_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package searcher

import (
	"testing"

	"github.com/blevesearch/bleve/v2/search"
)

func TestAgentFindPhrasePathsSmoke(t *testing.T) {
	loc := &search.Location{Pos: 2}
	p := phrasePath{{term: "quick", loc: loc}}
	paths := findPhrasePaths(0, nil, nil, nil, p, 0, nil)
	if len(paths) != 1 {
		t.Fatalf("paths len=%d want 1", len(paths))
	}
	if len(paths[0]) != 1 || paths[0][0].term != "quick" || paths[0][0].loc != loc {
		t.Fatalf("unexpected copied path: %#v", paths[0])
	}
}
GO

go test ./search/searcher -run TestAgentFindPhrasePathsSmoke -count=1
