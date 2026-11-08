#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_term_vector_locations_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
)

func main() {
	indexMapping := bleve.NewIndexMapping()
	textFieldMapping := bleve.NewTextFieldMapping()
	textFieldMapping.IncludeTermVectors = true
	indexMapping.DefaultMapping.AddFieldMappingsAt("body", textFieldMapping)

	idx, err := bleve.NewMemOnly(indexMapping)
	if err != nil {
		panic(err)
	}
	defer idx.Close()
	if err := idx.Index("doc1", map[string]interface{}{"body": "test document with text"}); err != nil {
		panic(err)
	}

	q := bleve.NewTermQuery("test")
	q.SetField("body")
	req := bleve.NewSearchRequest(q)
	req.IncludeLocations = true
	res, err := idx.Search(req)
	if err != nil {
		panic(err)
	}
	if res.Total != 1 || len(res.Hits) != 1 {
		fmt.Printf("term vector smoke total=%d hits=%d\n", res.Total, len(res.Hits))
		os.Exit(1)
	}
	if _, ok := res.Hits[0].Locations["body"]; !ok {
		fmt.Printf("missing body locations: %#v\n", res.Hits[0].Locations)
		os.Exit(1)
	}
	if _, bad := res.Hits[0].Locations[""]; bad {
		fmt.Printf("unexpected empty-field locations: %#v\n", res.Hits[0].Locations)
		os.Exit(1)
	}
	fmt.Println("term vector locations smoke passed")
}
GO

go run "$prog"
