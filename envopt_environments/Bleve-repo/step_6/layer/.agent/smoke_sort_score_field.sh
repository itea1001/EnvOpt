#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_sort_score_field_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"

	"github.com/blevesearch/bleve/v2"
)

func main() {
	m := bleve.NewIndexMapping()
	name := bleve.NewTextFieldMapping()
	name.Store = true
	m.DefaultMapping.AddFieldMappingsAt("name", name)

	idx, err := bleve.NewMemOnly(m)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	defer idx.Close()

	for id, doc := range map[string]map[string]interface{}{
		"1": {"name": "alice", "body": "needle needle"},
		"2": {"name": "bob", "body": "needle"},
		"3": {"name": "charlie", "body": "needle"},
	} {
		if err := idx.Index(id, doc); err != nil {
			fmt.Println(err)
			os.Exit(1)
		}
	}

	req := bleve.NewSearchRequest(bleve.NewMatchQuery("needle"))
	req.SortBy([]string{"-_score", "name"})
	req.Size = 2
	res, err := idx.Search(req)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	if len(res.Hits) != 2 {
		fmt.Printf("first page len=%d want 2\n", len(res.Hits))
		os.Exit(1)
	}
	for _, hit := range res.Hits {
		if len(hit.Sort) != 2 {
			fmt.Printf("hit %s sort len=%d values=%v want score+name values\n", hit.ID, len(hit.Sort), hit.Sort)
			os.Exit(1)
		}
	}

	req2 := bleve.NewSearchRequest(bleve.NewMatchQuery("needle"))
	req2.SortBy([]string{"-_score", "name"})
	req2.Size = 2
	req2.SearchAfter = res.Hits[0].Sort
	res2, err := idx.Search(req2)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	if len(res2.Hits) == 0 {
		fmt.Println("search_after with score+field sort returned no hits")
		os.Exit(1)
	}

	fmt.Println("sort score+field smoke passed")
}
GO

go run "$prog"
