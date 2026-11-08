#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_geoshape_mapping_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/document"
)

func main() {
	indexMapping := bleve.NewIndexMapping()
	docMapping := bleve.NewDocumentMapping()
	docMapping.AddFieldMappingsAt("location", bleve.NewGeoShapeFieldMapping())
	indexMapping.DefaultMapping = docMapping

	doc := document.NewDocument("doc1")
	data := map[string]interface{}{
		"location": map[string]interface{}{
			"type":        "point",
			"coordinates": []float64{-122.4194, 37.7749},
		},
	}
	if err := indexMapping.MapDocument(doc, data); err != nil {
		panic(err)
	}

	for _, field := range doc.Fields {
		if field.Name() == "location" {
			if _, ok := field.(*document.GeoShapeField); ok {
				fmt.Println("geoshape mapping smoke emitted GeoShapeField")
				return
			}
		}
	}
	fmt.Printf("geoshape mapping smoke found %d fields, none were location GeoShapeField\n", len(doc.Fields))
	os.Exit(1)
}
GO

go run "$prog"
