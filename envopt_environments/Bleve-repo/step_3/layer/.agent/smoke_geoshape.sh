#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_geoshape_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/mapping"
	"github.com/blevesearch/bleve/v2/search/query"
)

func main() {
	path := os.TempDir() + "/bleve-geoshape-smoke.bleve"
	_ = os.RemoveAll(path)
	defer os.RemoveAll(path)

	indexMapping := bleve.NewIndexMapping()
	docMapping := bleve.NewDocumentMapping()
	docMapping.AddFieldMappingsAt("location", mapping.NewGeoShapeFieldMapping())
	indexMapping.DefaultMapping = docMapping

	idx, err := bleve.New(path, indexMapping)
	if err != nil {
		panic(err)
	}
	defer idx.Close()

	doc := map[string]interface{}{
		"location": map[string]interface{}{
			"type":        "point",
			"coordinates": []float64{-0.1, 51.5},
		},
	}
	if err := idx.Index("doc1", doc); err != nil {
		panic(err)
	}

	polygon := [][][][]float64{{{{-1, 51}, {1, 51}, {1, 52}, {-1, 52}, {-1, 51}}}}
	geoQuery, err := query.NewGeoShapeQuery(polygon, "polygon", "intersects")
	if err != nil {
		panic(err)
	}
	geoQuery.SetField("location")

	result, err := idx.Search(bleve.NewSearchRequest(geoQuery))
	if err != nil {
		panic(err)
	}
	fmt.Printf("geoshape smoke total=%d\n", result.Total)
	if result.Total != 1 {
		os.Exit(1)
	}
}
GO

go run "$prog"
