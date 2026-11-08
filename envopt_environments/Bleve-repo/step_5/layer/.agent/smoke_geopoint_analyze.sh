#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_geopoint_analyze_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2/document"
)

func main() {
	field := document.NewGeoPointField("location", nil, -74.0060, 40.7128)
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("geopoint Analyze panic: %v\n", r)
			os.Exit(1)
		}
	}()
	field.Analyze()
	if field.AnalyzedLength() == 0 {
		fmt.Println("geopoint Analyze produced no tokens")
		os.Exit(1)
	}
	fmt.Printf("geopoint Analyze smoke tokens=%d\n", field.AnalyzedLength())
}
GO

go run "$prog"
