#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_highlight_fragmenter_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/blevesearch/bleve/v2"
)

func main() {
	idx, err := bleve.NewMemOnly(bleve.NewIndexMapping())
	if err != nil {
		panic(err)
	}
	defer idx.Close()
	if err := idx.Index("doc1", map[string]interface{}{
		"name": "steve has <a> long & complicated name",
	}); err != nil {
		panic(err)
	}

	req := bleve.NewSearchRequest(bleve.NewMatchQuery("long"))
	req.Highlight = bleve.NewHighlight()
	req.Highlight.AddField("name")
	res, err := idx.Search(req)
	if err != nil {
		panic(err)
	}
	if res.Total != 1 || len(res.Hits) != 1 {
		fmt.Printf("highlight smoke total=%d hits=%d\n", res.Total, len(res.Hits))
		os.Exit(1)
	}
	frags := res.Hits[0].Fragments["name"]
	if len(frags) == 0 || frags[0] == "..." || !strings.Contains(frags[0], "<mark>long</mark>") {
		fmt.Printf("bad highlight fragments: %#v\n", res.Hits[0].Fragments)
		os.Exit(1)
	}
	fmt.Println("highlight fragmenter smoke passed")
}
GO

go run "$prog"
