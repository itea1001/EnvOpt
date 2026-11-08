#!/usr/bin/env bash
set -euo pipefail

test_file="search/collector/zz_agent_size_limit_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package collector

import (
	"testing"

	"github.com/blevesearch/bleve/v2/search"
)

func agentCompareScore(i, j *search.DocumentMatch) int {
	switch {
	case i.Score < j.Score:
		return -1
	case i.Score > j.Score:
		return 1
	default:
		return 0
	}
}

func checkStoreSizeLimit(t *testing.T, name string, add func(*search.DocumentMatch, int) *search.DocumentMatch, length func() int) {
	t.Helper()
	if removed := add(&search.DocumentMatch{ID: name + "-one", Score: 1}, 2); removed != nil {
		t.Fatalf("%s first add removed %s; store must not remove before exceeding size", name, removed.ID)
	}
	if length() != 1 {
		t.Fatalf("%s after first add len=%d want 1", name, length())
	}
	if removed := add(&search.DocumentMatch{ID: name + "-two", Score: 2}, 2); removed != nil {
		t.Fatalf("%s second add removed %s; store must allow exactly size entries", name, removed.ID)
	}
	if length() != 2 {
		t.Fatalf("%s after second add len=%d want 2", name, length())
	}
	if removed := add(&search.DocumentMatch{ID: name + "-three", Score: 3}, 2); removed == nil {
		t.Fatalf("%s third add should remove one entry after exceeding size", name)
	}
	if length() != 2 {
		t.Fatalf("%s after third add len=%d want 2", name, length())
	}
}

func TestAgentCollectorSizeLimitSmoke(t *testing.T) {
	s := newStoreSlice(2, agentCompareScore)
	checkStoreSizeLimit(t, "slice", s.AddNotExceedingSize, s.len)

	h := newStoreHeap(2, agentCompareScore)
	checkStoreSizeLimit(t, "heap", h.AddNotExceedingSize, h.Len)
}
GO

go test ./search/collector -run TestAgentCollectorSizeLimitSmoke -count=1
