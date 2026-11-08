#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_fuzzy_prefix_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/search/query"
)

func main() {
	idx, err := bleve.NewMemOnly(bleve.NewIndexMapping())
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	defer idx.Close()

	for id, text := range map[string]string{"1": "cat", "2": "car", "3": "ba"} {
		if err := idx.Index(id, map[string]interface{}{"text": text}); err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
	}

	q := query.NewFuzzyQuery("ca")
	q.SetField("text")
	q.SetPrefix(5)
	q.SetFuzziness(1)
	res, err := idx.Search(bleve.NewSearchRequest(q))
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	if res.Total < 3 {
		fmt.Printf("fuzzy prefix>=term returned %d hits, want at least 3 including non-prefix fuzzy matches\n", res.Total)
		os.Exit(1)
	}

	fmt.Println("fuzzy prefix smoke passed")
}
GO

go run "$prog"
