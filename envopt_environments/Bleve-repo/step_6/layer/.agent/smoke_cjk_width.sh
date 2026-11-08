#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_cjk_width_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2/analysis"
	"github.com/blevesearch/bleve/v2/analysis/lang/cjk"
)

func check(input, want string) {
	filter := cjk.NewCJKWidthFilter()
	out := filter.Filter(analysis.TokenStream{{Term: []byte(input)}})
	got := string(out[0].Term)
	fmt.Printf("%q -> %q want %q\n", input, got, want)
	if got != want {
		os.Exit(1)
	}
}

func main() {
	check("ｶﾞ", "ガ")
	check("ﾊﾟ", "パ")
	check("ＡＢＣ１２３", "ABC123")
}
GO

go run "$prog"
