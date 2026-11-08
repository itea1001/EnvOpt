#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_fuzzy_score_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"math"
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

	if err := idx.Index("1", map[string]interface{}{"text": "hello"}); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	q := bleve.NewFuzzyQuery("helo")
	q.SetField("text")
	q.SetFuzziness(1)
	res, err := idx.Search(bleve.NewSearchRequest(q))
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	if res.Total == 0 {
		fmt.Println("fuzzy edit-distance query returned no hits")
		os.Exit(1)
	}
	for _, hit := range res.Hits {
		if math.IsNaN(hit.Score) || math.IsInf(hit.Score, 0) {
			fmt.Printf("invalid fuzzy score for %s: %v\n", hit.ID, hit.Score)
			os.Exit(1)
		}
	}

	fmt.Println("fuzzy score smoke passed")
}
GO

go run "$prog"
