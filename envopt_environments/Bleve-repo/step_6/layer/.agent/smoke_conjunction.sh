#!/usr/bin/env bash
set -euo pipefail

test_file="search/searcher/zz_agent_conjunction_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package searcher

import (
	"context"
	"testing"

	"github.com/blevesearch/bleve/v2/search"
)

func TestAgentConjunctionEmptyOptimizationSmoke(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("NewConjunctionSearcher panicked for empty searchers: %v", r)
		}
	}()
	_, err := NewConjunctionSearcher(context.Background(), nil, nil, search.SearcherOptions{Score: "none"})
	if err != nil {
		t.Fatalf("NewConjunctionSearcher returned error: %v", err)
	}
}
GO

go test ./search/searcher -run TestAgentConjunctionEmptyOptimizationSmoke -count=1
