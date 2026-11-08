#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_ip_range_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"net"
	"os"

	"github.com/blevesearch/bleve/v2"
	"github.com/blevesearch/bleve/v2/search/query"
)

func mustTotal(idx bleve.Index, q *query.IPRangeQuery, field string, want uint64) {
	q.SetField(field)
	result, err := idx.Search(bleve.NewSearchRequest(q))
	if err != nil {
		panic(err)
	}
	fmt.Printf("%s total=%d want=%d\n", q.CIDR, result.Total, want)
	if result.Total != want {
		os.Exit(1)
	}
}

func main() {
	indexMapping := bleve.NewIndexMapping()
	docMapping := bleve.NewDocumentMapping()
	docMapping.AddFieldMappingsAt("ip", bleve.NewIPFieldMapping())
	indexMapping.DefaultMapping = docMapping

	idx, err := bleve.NewMemOnly(indexMapping)
	if err != nil {
		panic(err)
	}
	defer idx.Close()

	doc := map[string]interface{}{"ip": net.ParseIP("192.168.1.100")}
	if err := idx.Index("doc1", doc); err != nil {
		panic(err)
	}

	mustTotal(idx, bleve.NewIPRangeQuery("192.168.1.0/24"), "ip", 1)
	mustTotal(idx, bleve.NewIPRangeQuery("192.168.1.100"), "ip", 1)
	mustTotal(idx, bleve.NewIPRangeQuery("10.0.0.0/8"), "ip", 0)
}
GO

go run "$prog"
