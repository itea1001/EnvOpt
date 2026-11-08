#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_boltdb_open_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/blevesearch/bleve/v2"
	_ "github.com/blevesearch/bleve/v2/index/upsidedown"
	_ "github.com/blevesearch/bleve/v2/index/upsidedown/store/boltdb"
)

func main() {
	path := filepath.Join(os.TempDir(), "bleve-boltdb-smoke.bleve")
	_ = os.RemoveAll(path)
	defer os.RemoveAll(path)

	idx, err := bleve.NewUsing(path, bleve.NewIndexMapping(), "upsidedown", "boltdb", nil)
	if err != nil {
		panic(err)
	}
	defer idx.Close()

	if err := idx.Index("doc1", map[string]interface{}{"title": "Test Document"}); err != nil {
		panic(err)
	}
	fmt.Println("boltdb open smoke passed")
}
GO

go run "$prog"
