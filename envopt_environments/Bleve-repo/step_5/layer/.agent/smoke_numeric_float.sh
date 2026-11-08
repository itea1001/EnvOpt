#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_numeric_float_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"math"
	"os"
	"sort"

	"github.com/blevesearch/bleve/v2/numeric"
)

func main() {
	values := []float64{-2.5, -1.5, -0.5, 0, 0.5, 1.5, 2.5}
	keys := make([]int64, len(values))
	for i, v := range values {
		keys[i] = numeric.Float64ToInt64(v)
		got := numeric.Int64ToFloat64(keys[i])
		if math.Float64bits(got) != math.Float64bits(v) {
			fmt.Printf("round trip %v -> %d -> %v\n", v, keys[i], got)
			os.Exit(1)
		}
	}
	if !sort.SliceIsSorted(keys, func(i, j int) bool { return keys[i] < keys[j] }) {
		fmt.Printf("float keys not sorted with values: values=%v keys=%v\n", values, keys)
		os.Exit(1)
	}
	fmt.Println("numeric float smoke passed")
}
GO

go run "$prog"
