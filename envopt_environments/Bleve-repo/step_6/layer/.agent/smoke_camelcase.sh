#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_camelcase_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/blevesearch/bleve/v2/analysis"
	"github.com/blevesearch/bleve/v2/analysis/token/camelcase"
)

func main() {
	filter := camelcase.NewCamelCaseFilter()
	stream := analysis.TokenStream{&analysis.Token{Term: []byte("camelCaseWord"), Start: 0, End: 13}}
	gotStream := filter.Filter(stream)
	got := make([]string, len(gotStream))
	for i, tok := range gotStream {
		got[i] = string(tok.Term)
		if tok.Start < 0 || tok.End < tok.Start || tok.End > 13 {
			fmt.Printf("bad offsets for %q: %d-%d\n", tok.Term, tok.Start, tok.End)
			os.Exit(1)
		}
	}
	if strings.Join(got, ",") != "camel,Case,Word" {
		fmt.Printf("tokens=%v want [camel Case Word]\n", got)
		os.Exit(1)
	}
	fmt.Println("camelcase smoke passed")
}
GO

go run "$prog"
