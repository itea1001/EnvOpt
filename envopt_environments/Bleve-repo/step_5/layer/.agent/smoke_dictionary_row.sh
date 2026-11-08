#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_dictionary_row_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"bytes"
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2/index/upsidedown"
)

func main() {
	row := upsidedown.NewDictionaryRow([]byte("hello"), 7, 3)
	parsed, err := upsidedown.NewDictionaryRowK(row.Key())
	if err != nil {
		fmt.Printf("NewDictionaryRowK returned error for valid key: %v\n", err)
		os.Exit(1)
	}
	if parsed == nil {
		fmt.Println("NewDictionaryRowK returned nil row for valid key")
		os.Exit(1)
	}
	if !bytes.Equal(parsed.Key(), row.Key()) {
		fmt.Printf("parsed key mismatch got=%v want=%v\n", parsed.Key(), row.Key())
		os.Exit(1)
	}
	fmt.Println("dictionary row smoke passed")
}
GO

go run "$prog"
