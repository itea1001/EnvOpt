#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_extract_circle_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2/geo"
)

func main() {
	input := map[string]interface{}{
		"coordinates": []float64{-122.4194, 37.7749},
		"radius":      "1km",
	}
	shape, ok := geo.ExtractCircle(input)
	fmt.Printf("ExtractCircle shape=%v ok=%v\n", shape, ok)
	if !ok || shape == nil || len(shape.Center) != 2 || shape.Radius != "1km" {
		os.Exit(1)
	}
}
GO

go run "$prog"
