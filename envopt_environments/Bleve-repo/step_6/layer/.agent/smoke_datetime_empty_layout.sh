#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_datetime_empty_layout_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"
	"time"

	"github.com/blevesearch/bleve/v2"
)

func main() {
	im := bleve.NewIndexMapping()
	dm := bleve.NewDocumentMapping()
	fm := bleve.NewDateTimeFieldMapping()
	fm.DateFormat = ""
	fm.Store = true
	dm.AddFieldMappingsAt("created_at", fm)
	im.DefaultMapping = dm

	idx, err := bleve.NewMemOnly(im)
	if err != nil {
		panic(err)
	}
	defer idx.Close()

	ts := time.Date(2024, 3, 4, 5, 6, 7, 0, time.UTC)
	if err := idx.Index("doc1", map[string]interface{}{"created_at": ts}); err != nil {
		panic(err)
	}

	req := bleve.NewSearchRequest(bleve.NewMatchAllQuery())
	req.Fields = []string{"created_at"}
	res, err := idx.Search(req)
	if err != nil {
		panic(err)
	}
	if len(res.Hits) != 1 {
		fmt.Printf("hits=%d want 1\n", len(res.Hits))
		os.Exit(1)
	}
	got, _ := res.Hits[0].Fields["created_at"].(string)
	want := ts.Format(time.RFC3339)
	if got != want {
		fmt.Printf("created_at=%q want %q\n", got, want)
		os.Exit(1)
	}
	fmt.Println("datetime empty layout smoke passed")
}
GO

go run "$prog"
