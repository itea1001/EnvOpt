#!/usr/bin/env bash
set -euo pipefail

test_file="index/upsidedown/zz_agent_backindex_protobuf_smoke_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package upsidedown

import (
	"testing"

	proto "github.com/golang/protobuf/proto"
)

func TestAgentBackIndexFieldTermsSmoke(t *testing.T) {
	value := &BackIndexRowValue{
		TermsEntries: []*BackIndexTermsEntry{
			{Field: proto.Uint32(1), Terms: []string{"alpha", "beta"}},
			{Field: proto.Uint32(300), Terms: []string{"wide-field"}},
		},
	}
	data, err := proto.Marshal(value)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	row, err := NewBackIndexRowKV(NewBackIndexRow([]byte("doc"), nil, nil).Key(), data)
	if err != nil {
		t.Fatalf("NewBackIndexRowKV valid protobuf: %v", err)
	}
	if got, want := len(row.AllTermKeys()), 3; got != want {
		t.Fatalf("term key count=%d want %d", got, want)
	}
}

func TestAgentBackIndexFieldTermsRejectsMalformedSmoke(t *testing.T) {
	callback := func(field uint32, term []byte) {}
	cases := [][]byte{
		{0x08},
		{0x12, 0xff, 0xff, 0xff},
		{0x12, 0x04, 't'},
	}
	for _, data := range cases {
		if err := visitBackIndexRowFieldTerms(data, callback); err == nil {
			t.Fatalf("visitBackIndexRowFieldTerms(%v) returned nil error", data)
		}
	}
}
GO

go test ./index/upsidedown -run 'TestAgentBackIndexFieldTerms' -count=1 -timeout=10s
