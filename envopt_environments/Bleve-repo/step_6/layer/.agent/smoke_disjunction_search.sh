#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_disjunction_search_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
)

func main() {
	idx, err := bleve.NewMemOnly(bleve.NewIndexMapping())
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	defer idx.Close()

	_ = idx.Index("doc1", map[string]interface{}{"name": "apple", "type": "fruit"})
	_ = idx.Index("doc2", map[string]interface{}{"name": "banana", "type": "fruit"})
	_ = idx.Index("doc3", map[string]interface{}{"name": "carrot", "type": "vegetable"})

	matchReq := bleve.NewSearchRequest(bleve.NewMatchQuery("fruit"))
	matchReq.Size = 10
	matchRes, err := idx.Search(matchReq)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	if matchRes.Total != 2 {
		fmt.Printf("match query total=%d want 2\n", matchRes.Total)
		os.Exit(1)
	}

	orReq := bleve.NewSearchRequest(bleve.NewDisjunctionQuery(
		bleve.NewMatchQuery("apple"),
		bleve.NewMatchQuery("carrot"),
	))
	orReq.Size = 10
	orRes, err := idx.Search(orReq)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	if orRes.Total == 0 {
		fmt.Printf("disjunction total=%d want nonzero\n", orRes.Total)
		os.Exit(1)
	}

	fmt.Println("disjunction search smoke passed")
}
GO

go run "$prog"
