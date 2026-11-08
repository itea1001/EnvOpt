#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_boolean_field_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2/document"
)

func main() {
	for _, want := range []bool{true, false} {
		field := document.NewBooleanField("b", want)
		got, err := field.Boolean()
		if err != nil {
			fmt.Printf("Boolean() returned error for %v: %v\n", want, err)
			os.Exit(1)
		}
		if got != want {
			fmt.Printf("Boolean()=%v want %v\n", got, want)
			os.Exit(1)
		}
	}
	fmt.Println("boolean field smoke passed")
}
GO

go run "$prog"
