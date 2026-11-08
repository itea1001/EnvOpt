# Bleve Fast Navigation

Use this only if direct `rg` from the bug report is not enough.

Common areas:
- datetime percent formats: `analysis/datetime/percent/percent.go`
- language analyzers: `analysis/lang/<lang>/`, token filters and stemmers under that package
- CJK width normalization: `analysis/lang/cjk/cjk_width.go`; validate with `.agent/smoke_cjk_width.sh`
- Polish Stempel trie/data loading: `analysis/lang/pl/stempel/`
- Arabic normalization: `analysis/lang/ar/arabic_normalize.go`
- Turkish analyzer construction: `analysis/lang/tr/analyzer_tr.go`
- timestamp datetime parsers: `analysis/datetime/timestamp/`; seconds parser smoke: `.agent/smoke_timestamp_seconds.sh`
- search request JSON and facets: root `search.go`, `search_no_knn.go`, `search_knn.go`
- root indexing API and empty document IDs: `index_impl.go`; validate with `.agent/smoke_index_id.sh`
- sort parsing: `search/sort.go`
- collectors and hit ordering: `search/collector/`; heap capacity lives in `search/collector/heap.go`
- Levenshtein/fuzzy matching: `search/levenshtein.go`
- query string lexer/parser: `search/query/query_string_lex.go`, generated parser files nearby
- phrase search path matching: `search/searcher/search_phrase.go`
- conjunction/disjunction optimization: `search/searcher/search_conjunction.go`, `search/searcher/search_disjunction.go`
- numeric range searcher: `search/searcher/search_numeric_range.go`
- IP range/CIDR searcher: `search/searcher/search_ip_range.go`
- geo bounding box searcher: `search/searcher/search_geoboundingbox.go`
- geo distance rectangles and utilities: `geo/geo.go`, `geo/geo_dist.go`
- geo point parsing helpers: `geo/parse.go`; validate with `.agent/smoke_extract_geopoint.sh`
- document geo fields: `document/field_geoshape.go`, `document/field_geopoint.go`; GeoPoint Analyze smoke: `.agent/smoke_geopoint_analyze.sh`
- geoshape mapping/indexing: `mapping/field.go` `processGeoShape`; validate field emission with `.agent/smoke_geoshape_mapping.sh`
- scorch TermFieldReader/postings internals: `index/scorch/snapshot_index.go`
- upsidedown index internals: `index/upsidedown/`
- BoltDB upsidedown store open/initialization: `index/upsidedown/store/boltdb/`; validate with `.agent/smoke_boltdb_open.sh`
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
