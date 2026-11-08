# Bleve Fast Navigation

Use this only if direct `rg` from the bug report is not enough.

Common areas:
- datetime percent formats: `analysis/datetime/percent/percent.go`
- language analyzers: `analysis/lang/<lang>/`, token filters and stemmers under that package
- Polish Stempel trie/data loading: `analysis/lang/pl/stempel/`
- Arabic normalization: `analysis/lang/ar/arabic_normalize.go`
- Turkish analyzer construction: `analysis/lang/tr/analyzer_tr.go`
- search request JSON and facets: root `search.go`, `search_no_knn.go`, `search_knn.go`
- sort parsing: `search/sort.go`
- collectors and hit ordering: `search/collector/`
- Levenshtein/fuzzy matching: `search/levenshtein.go`
- query string lexer/parser: `search/query/query_string_lex.go`, generated parser files nearby
- numeric range searcher: `search/searcher/search_numeric_range.go`
- IP range/CIDR searcher: `search/searcher/search_ip_range.go`
- geo bounding box searcher: `search/searcher/search_geoboundingbox.go`
- geo distance rectangles and utilities: `geo/geo.go`, `geo/geo_dist.go`
- document geo fields: `document/field_geoshape.go`, `document/field_geopoint.go`
- upsidedown index internals: `index/upsidedown/`
- property path reflection/mapping: `mapping/reflect.go`

Useful commands:
- `rg -n --glob '*.go' 'SymbolOrErrorText' .`
- `rg -n --glob '*.go' 'func Name|type Name|Name\\(' package/dir`
- `.agent/test_changed.sh` after editing source

Validation rule of thumb:
- one package touched: `go test ./that/package`
- parser/lexer touched: `go test ./search/query`
- searcher touched: `go test ./search/searcher`
- root search request touched: `go test . ./search`
- analyzer touched: `go test ./analysis/lang/<lang>/...`
