#!/usr/bin/env bash
set -euo pipefail

test_file="search/collector/zz_agent_heap_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package collector

import (
	"testing"

	"github.com/blevesearch/bleve/v2/search"
)

func TestAgentHeapAddNotExceedingSizeSmoke(t *testing.T) {
	h := newStoreHeap(2, func(i, j *search.DocumentMatch) int {
		switch {
		case i.Score < j.Score:
			return -1
		case i.Score > j.Score:
			return 1
		default:
			return 0
		}
	})
	if removed := h.AddNotExceedingSize(&search.DocumentMatch{ID: "one", Score: 1}, 2); removed != nil {
		t.Fatalf("first add removed %s; heap must not remove before exceeding size", removed.ID)
	}
	if h.Len() != 1 {
		t.Fatalf("after first add len=%d want 1", h.Len())
	}
	if removed := h.AddNotExceedingSize(&search.DocumentMatch{ID: "two", Score: 2}, 2); removed != nil {
		t.Fatalf("second add removed %s; heap must allow exactly size entries", removed.ID)
	}
	if h.Len() != 2 {
		t.Fatalf("after second add len=%d want 2", h.Len())
	}
	if removed := h.AddNotExceedingSize(&search.DocumentMatch{ID: "three", Score: 3}, 2); removed == nil {
		t.Fatalf("third add should remove one entry after exceeding size")
	}
	if h.Len() != 2 {
		t.Fatalf("after third add len=%d want 2", h.Len())
	}
}
GO

go test ./search/collector -run TestAgentHeapAddNotExceedingSizeSmoke -count=1
