#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_scorch_termreader_smoke.go"
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

	for id, body := range map[string]string{
		"doc1": "hello world",
		"doc2": "hello bleve",
	} {
		if err := idx.Index(id, map[string]interface{}{"body": body}); err != nil {
			panic(err)
		}
	}

	q := bleve.NewTermQuery("hello")
	q.SetField("body")
	res, err := idx.Search(bleve.NewSearchRequest(q))
	if err != nil {
		panic(err)
	}
	fmt.Printf("scorch termreader smoke total=%d\n", res.Total)
	if res.Total == 0 {
		os.Exit(1)
	}
}
GO

go run "$prog"
