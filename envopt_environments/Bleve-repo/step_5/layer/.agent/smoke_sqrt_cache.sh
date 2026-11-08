#!/usr/bin/env bash
set -euo pipefail

test_file="search/scorer/zz_agent_sqrt_cache_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package scorer

import (
	"math"
	"testing"

	"github.com/blevesearch/bleve/v2/search"
	index "github.com/blevesearch/bleve_index_api"
)

func TestAgentTermScorerSqrtCacheBoundarySmoke(t *testing.T) {
	scorer := &TermQueryScorer{
		queryTerm:    "term",
		queryField:   "field",
		idf:          1,
		includeScore: true,
		queryNorm:    1,
		queryWeight:  1,
	}
	ctx := &search.SearchContext{DocumentMatchPool: search.NewDocumentMatchPool(1, 0)}
	match := &index.TermFieldDoc{
		ID:   "doc",
		Freq: MaxSqrtCache + 1,
		Norm: 1,
	}
	got := scorer.Score(ctx, match)
	if got == nil {
		t.Fatalf("Score returned nil")
	}
	want := math.Sqrt(float64(MaxSqrtCache + 1))
	if math.Abs(got.Score-want) > 0.0000001 {
		t.Fatalf("score=%f want %f", got.Score, want)
	}
}
GO

go test ./search/scorer -run TestAgentTermScorerSqrtCacheBoundarySmoke -count=1
