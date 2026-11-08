#!/usr/bin/env bash
set -euo pipefail

test_file="search/searcher/zz_agent_phrase_advance_nil_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package searcher

import (
	"testing"

	"github.com/blevesearch/bleve/v2/search"
	index "github.com/blevesearch/bleve_index_api"
)

type agentNilAdvanceSearcher struct {
	advanced bool
}

func (s *agentNilAdvanceSearcher) Next(ctx *search.SearchContext) (*search.DocumentMatch, error) {
	return nil, nil
}
func (s *agentNilAdvanceSearcher) Advance(ctx *search.SearchContext, ID index.IndexInternalID) (*search.DocumentMatch, error) {
	s.advanced = true
	return nil, nil
}
func (s *agentNilAdvanceSearcher) Close() error { return nil }
func (s *agentNilAdvanceSearcher) Weight() float64 { return 1 }
func (s *agentNilAdvanceSearcher) SetQueryNorm(float64) {}
func (s *agentNilAdvanceSearcher) Count() uint64 { return 0 }
func (s *agentNilAdvanceSearcher) Min() int { return 0 }
func (s *agentNilAdvanceSearcher) Size() int { return 0 }
func (s *agentNilAdvanceSearcher) DocumentMatchPoolSize() int { return 0 }

func TestAgentPhraseAdvanceNilCurrMustSmoke(t *testing.T) {
	must := &agentNilAdvanceSearcher{}
	ps := &PhraseSearcher{
		mustSearcher: must,
		initialized:  true,
	}
	ctx := &search.SearchContext{DocumentMatchPool: search.NewDocumentMatchPool(1, 0)}
	got, err := ps.Advance(ctx, index.IndexInternalID("doc-2"))
	if err != nil {
		t.Fatalf("Advance returned error: %v", err)
	}
	if got != nil {
		t.Fatalf("Advance returned %#v want nil", got)
	}
	if !must.advanced {
		t.Fatalf("Advance did not call mustSearcher.Advance")
	}
}
GO

go test ./search/searcher -run TestAgentPhraseAdvanceNilCurrMustSmoke -count=1
