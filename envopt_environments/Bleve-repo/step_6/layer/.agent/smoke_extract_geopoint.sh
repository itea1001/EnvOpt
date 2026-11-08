#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_extract_geopoint_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2/geo"
)

func check(input interface{}, want bool) {
	lon, lat, ok := geo.ExtractGeoPoint(input)
	fmt.Printf("ExtractGeoPoint(%v) lon=%f lat=%f ok=%v want=%v\n", input, lon, lat, ok, want)
	if ok != want {
		os.Exit(1)
	}
}

func main() {
	check("12.974872,77.607749", true)
	check("invalid,coordinates", false)
	check("12.974872,invalid", false)
	check([]interface{}{12.974872, 77.607749}, true)
	check([]interface{}{12.974872, "invalid"}, false)
}
GO

go run "$prog"
