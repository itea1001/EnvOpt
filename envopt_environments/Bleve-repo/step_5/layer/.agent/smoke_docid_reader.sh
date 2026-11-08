#!/usr/bin/env bash
set -euo pipefail

test_file="index/upsidedown/zz_agent_docid_reader_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package upsidedown

import "testing"

func TestAgentDocIDReaderNextOnlySmoke(t *testing.T) {
	r := &UpsideDownCouchDocIDReader{only: []string{"a", "a", "b"}}
	if ok := r.nextOnly(); !ok {
		t.Fatalf("nextOnly returned false before distinct next id; onlyPos=%d", r.onlyPos)
	}
	if r.onlyPos != 2 {
		t.Fatalf("nextOnly onlyPos=%d want 2", r.onlyPos)
	}
	if ok := r.nextOnly(); ok {
		t.Fatalf("nextOnly returned true at end; onlyPos=%d", r.onlyPos)
	}
	if r.onlyPos != 3 {
		t.Fatalf("nextOnly final onlyPos=%d want 3", r.onlyPos)
	}
}
GO

go test ./index/upsidedown -run TestAgentDocIDReaderNextOnlySmoke -count=1
