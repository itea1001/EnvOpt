#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_mapping_path_smoke.go"
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
		panic(err)
	}
	defer idx.Close()

	if err := idx.Index("doc1", map[string]interface{}{"field": "test value"}); err != nil {
		panic(err)
	}
	res, err := idx.Search(bleve.NewSearchRequest(bleve.NewMatchQuery("test")))
	if err != nil {
		panic(err)
	}
	fmt.Printf("mapping path smoke total=%d\n", res.Total)
	if res.Total != 1 {
		os.Exit(1)
	}
}
GO

go run "$prog"
