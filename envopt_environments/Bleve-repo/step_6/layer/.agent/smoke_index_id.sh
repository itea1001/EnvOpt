#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_index_id_smoke.go"
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

	if err := idx.Index("doc1", map[string]interface{}{"title": "ok"}); err != nil {
		fmt.Printf("non-empty id rejected: %v\n", err)
		os.Exit(1)
	}
	if err := idx.Index("", map[string]interface{}{"title": "bad"}); err == nil {
		fmt.Println("empty id accepted")
		os.Exit(1)
	}
	fmt.Println("index id smoke passed")
}
GO

go run "$prog"
