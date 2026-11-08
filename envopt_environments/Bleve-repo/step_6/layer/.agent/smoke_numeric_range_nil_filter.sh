#!/usr/bin/env bash
set -euo pipefail

test_file="search/searcher/zz_agent_numeric_range_nil_filter_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package searcher

import "testing"

func TestAgentTermRangeEnumerateNilFilterSmoke(t *testing.T) {
	tr := &termRange{
		startTerm: []byte{0x10},
		endTerm:   []byte{0x12},
	}
	terms := tr.Enumerate(nil)
	if len(terms) != 3 {
		t.Fatalf("Enumerate(nil) len=%d want 3", len(terms))
	}
	for i, term := range terms {
		want := byte(0x10 + i)
		if len(term) != 1 || term[0] != want {
			t.Fatalf("term %d=%v want [%#x]", i, term, want)
		}
	}
}
GO

go test ./search/searcher -run TestAgentTermRangeEnumerateNilFilterSmoke -count=1
