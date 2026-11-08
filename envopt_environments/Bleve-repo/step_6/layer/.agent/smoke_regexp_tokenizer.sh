#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_regexp_tokenizer_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/blevesearch/bleve/v2/analysis/tokenizer/regexp"
)

func main() {
	tok, err := regexp.NewRegexpTokenizer(`\w+`)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	stream := tok.Tokenize([]byte("hello world test"))
	got := make([]string, len(stream))
	for i, token := range stream {
		got[i] = string(token.Term)
	}
	if strings.Join(got, ",") != "hello,world,test" {
		fmt.Printf("tokens=%v want [hello world test]\n", got)
		os.Exit(1)
	}
	fmt.Println("regexp tokenizer smoke passed")
}
GO

go run "$prog"
