#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_field_mapping_lookup_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
)

func main() {
	im := bleve.NewIndexMapping()
	docMapping := bleve.NewDocumentMapping()
	propertyMapping := bleve.NewDocumentMapping()
	textField := bleve.NewTextFieldMapping()
	textField.Name = ""
	propertyMapping.AddFieldMappingsAt("title", textField)
	docMapping.AddSubDocumentMapping("title", propertyMapping)
	im.DefaultMapping = docMapping

	field := im.FieldMappingForPath("title")
	if field.Type != "text" {
		fmt.Printf("FieldMappingForPath(title) returned %#v\n", field)
		os.Exit(1)
	}
	fmt.Println("field mapping lookup smoke passed")
}
GO

go run "$prog"
