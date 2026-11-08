#!/usr/bin/env python3
"""Small Bleve bug-localization helper for Claude Code.

Pass a few exact report words/symbols. The script ranks likely Go files using
path hints, symbol/text matches, and Bleve subsystem knowledge, then prints
compact line evidence plus validation commands.
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path.cwd()

STOP = {
    "the", "and", "or", "but", "with", "when", "from", "into", "that",
    "this", "should", "actual", "expected", "error", "panic", "runtime",
    "search", "query", "index", "field", "value", "values", "returns",
    "return", "fails", "incorrect", "broken", "causes", "using", "code",
}

HINTS = {
    "arabic": ["analysis/lang/ar/analyzer_ar.go", "analysis/lang/ar/arabic_normalize.go"],
    "analyzer": ["analysis/lang/", "analysis/token/"],
    "addnotexceedingsize": ["search/collector/slice.go", "search/collector/heap.go", "search/collector/topn.go"],
    "backindex": ["index/upsidedown/back_index.go", "index/upsidedown/upsidedown.go"],
    "backindexrow": ["index/upsidedown/row.go"],
    "visitbackindexrowfieldterms": ["index/upsidedown/row.go"],
    "back": ["index/upsidedown/"],
    "booleanfield": ["document/field_boolean.go"],
    "booleanquery": ["search/query/boolean.go"],
    "boolean": ["search/query/boolean.go", "search/searcher/search_boolean.go"],
    "boltdb": ["index/upsidedown/store/boltdb/"],
    "bolt": ["index/upsidedown/store/boltdb/"],
    "cidr": ["search/query/ip_range.go", "search/searcher/search_ip_range.go", "document/field_ip.go"],
    "cjk": ["analysis/lang/cjk/cjk_width.go", "analysis/lang/cjk/"],
    "collector": ["search/collector/"],
    "camelcase": ["analysis/token/camelcase/camelcase.go"],
    "conjunction": ["search/searcher/search_conjunction.go"],
    "dictionary": ["index/scorch/snapshot_index_dict.go", "index_impl.go", "index_alias_impl.go"],
    "dict": ["index/scorch/snapshot_index_dict.go"],
    "disjunction": ["search/searcher/search_disjunction_slice.go", "search/searcher/search_disjunction.go", "search/query/disjunction.go"],
    "disjunctionslicesearcher": ["search/searcher/search_disjunction_slice.go"],
    "datetimeparsernamed": ["mapping/index.go"],
    "iso": ["analysis/datetime/iso/"],
    "datetime": ["index_impl.go", "mapping/field.go", "analysis/datetime/"],
    "datetimefield": ["index_impl.go", "document/field_datetime.go", "mapping/field.go"],
    "externalid": ["search/collector/topn.go"],
    "exceptions": ["analysis/tokenizer/exception/exception.go"],
    "exceptionstokenizer": ["analysis/tokenizer/exception/exception.go"],
    "exception": ["analysis/tokenizer/exception/exception.go"],
    "extractgeopoint": ["geo/parse.go"],
    "extractcircle": ["geo/parse.go"],
    "fieldcache": ["index/scorch/field_cache.go"],
    "fielddescribedbypath": ["mapping/document.go"],
    "fieldmappingforpath": ["mapping/index.go", "mapping/document.go"],
    "getfieldname": ["mapping/field.go"],
    "findphrasepaths": ["search/searcher/search_phrase.go"],
    "fuzzy": ["search/searcher/search_fuzzy.go", "search/query/fuzzy.go", "search/levenshtein.go"],
    "float64toint64": ["numeric/float.go"],
    "getref": ["analysis/lang/pl/stempel/row.go"],
    "indexalias": ["index_alias_impl.go"],
    "int64tofloat64": ["numeric/float.go"],
    "float": ["numeric/float.go"],
    "forcemerge": ["index/scorch/scorch.go", "index/scorch/mergeplan/"],
    "fragmenter": ["search/highlight/fragmenter/"],
    "geoboundingbox": ["search/searcher/search_geoboundingbox.go"],
    "geohash": ["geo/geohash.go"],
    "geopoint": ["document/field_geopoint.go", "search/searcher/search_geopointdistance.go"],
    "geopointfield": ["document/field_geopoint.go"],
    "geoshape": ["mapping/field.go", "search/searcher/search_geoshape.go", "search/query/geo_shape.go", "document/field_geoshape.go", "geo/"],
    "geojson": ["geo/parse.go", "document/field_geoshape.go", "search/searcher/search_geoshape.go"],
    "heap": ["search/collector/heap.go"],
    "highlight": ["search/highlight/"],
    "highlighter": ["search/highlight/", "registry/highlight.go"],
    "iprange": ["search/query/ip_range.go", "search/searcher/search_ip_range.go"],
    "ip": ["search/query/ip_range.go", "search/searcher/search_ip_range.go", "document/field_ip.go", "mapping/field.go"],
    "iterator": ["index/upsidedown/store/", "index/scorch/snapshot_index_dict.go"],
    "levenshtein": ["search/levenshtein.go"],
    "marshal": ["index/upsidedown/"],
    "marshaling": ["index/upsidedown/"],
    "maxerrors": ["index/upsidedown/store/metrics/"],
    "metrics": ["index/upsidedown/store/metrics/"],
    "moss": ["index/upsidedown/store/moss/"],
    "portuguese": ["analysis/lang/pt/"],
    "prefix": ["index/upsidedown/store/", "search/searcher/search_term_prefix.go"],
    "property": ["mapping/document.go", "mapping/reflect.go"],
    "phrase": ["search/searcher/search_phrase.go", "search/query/phrase.go"],
    "postings": ["index/scorch/snapshot_index.go"],
    "regexp": ["analysis/tokenizer/regexp/regexp.go"],
    "reverse": ["analysis/token/reverse/reverse.go"],
    "numericrangequery": ["search/query/numeric_range.go"],
    "maxsqrtcache": ["search/scorer/scorer_term.go", "search/scorer/sqrt_cache.go"],
    "score": ["search/scorer/", "search/searcher/", "search/query/"],
    "snapshot": ["index/scorch/"],
    "sqrtcache": ["search/scorer/scorer_term.go", "search/scorer/sqrt_cache.go"],
    "stempel": ["analysis/lang/pl/stempel/"],
    "stemmer": ["analysis/lang/"],
    "termvector": ["index/upsidedown/upsidedown.go", "search/scorer/scorer_term.go", "search/search.go"],
    "locations": ["search/search.go", "search/util.go", "index/upsidedown/upsidedown.go"],
    "termfieldreader": ["index/scorch/snapshot_index.go", "index/upsidedown/reader.go"],
    "termrange": ["search/searcher/search_disjunction.go", "search/searcher/search_term_range.go", "search/searcher/search_multi_term.go", "search/query/term_range.go"],
    "termrangequery": ["search/query/term_range.go", "search/searcher/search_term_range.go", "search/searcher/search_disjunction.go"],
    "thesaurus": ["index/scorch/snapshot_index.go"],
    "thesauruskeys": ["index/scorch/snapshot_index.go"],
    "nextonly": ["index/upsidedown/reader.go"],
    "docidreader": ["index/upsidedown/reader.go", "index/upsidedown/index_reader.go"],
    "topncollector": ["search/collector/topn.go", "search/collector/heap.go"],
    "upsidedown": ["index/upsidedown/"],
    "width": ["analysis/lang/cjk/cjk_width.go"],
    "synonym": ["pre_search.go", "index_alias_impl.go", "search.go"],
    "synonymsourceconstructor": ["mapping/synonym.go"],
    "presearch": ["pre_search.go", "index_alias_impl.go"],
    "currmust": ["search/searcher/search_phrase.go"],
}

API_NOTES = {
    "float64toint64": [
        "Sortable float encodings live in numeric/float.go. Use .agent/smoke_numeric_float.sh; it checks negative ordering and Int64ToFloat64 round trips.",
    ],
    "int64tofloat64": [
        "Sortable float encodings live in numeric/float.go. Use .agent/smoke_numeric_float.sh; it checks negative ordering and Int64ToFloat64 round trips.",
    ],
    "float": [
        "Float sorting/storage bugs usually mean numeric/float.go, not document/field_geopoint.go. Use .agent/smoke_numeric_float.sh.",
    ],
    "geoshape": [
        "GeoShape search often crosses document/field_geoshape.go, search/query/geo_shape.go, and search/searcher/search_geoshape.go.",
        "GeoShape mapping/indexing bugs usually cross mapping/field.go processGeoShape and document/field_geoshape.go; validate field emission with .agent/smoke_geoshape_mapping.sh.",
        "For comparisons, peer doc-value filters live in search_geoboundingbox.go, search_geopolygon.go, and search_geopointdistance.go.",
        "Doc-value shape bytes are wrapped with geo.GlueBytes markers. For zero-result geoshape searcher bugs, focus on the continuation/read-finished state transition and use .agent/smoke_geoshape.sh.",
    ],
    "ip": [
        "IP fields require IP field mapping and net.IP values; query parsing is in search/query/ip_range.go, term search in search/searcher/search_ip_range.go.",
        "Use .agent/smoke_ip_range.sh after IP range query edits; it checks CIDR match, exact IP match, and nonmatching CIDR with the correct IP field mapping.",
    ],
    "dictionary": [
        "Public dictionary iteration is Index.FieldDict(...); scorch merging logic is in index/scorch/snapshot_index_dict.go.",
        "Upsidedown row parsing bugs named NewDictionaryRowK/NewDictionaryRowKV live in index/upsidedown/row.go; use .agent/smoke_dictionary_row.sh.",
    ],
    "fielddescribedbypath": [
        "Document mapping field lookup is in mapping/document.go; FieldMappingForPath calls it from mapping/index.go. Use .agent/smoke_field_mapping_lookup.sh.",
    ],
    "property": [
        "Property/path mapping bugs usually live in mapping/document.go. Use .agent/smoke_mapping_path.sh for empty path elements and .agent/smoke_field_mapping_lookup.sh for property-name field lookup.",
    ],
    "mapping": [
        "Document mapping path bugs usually live in mapping/document.go. Use .agent/smoke_mapping_path.sh for empty path elements and .agent/smoke_field_mapping_lookup.sh for property-name field lookup.",
    ],
    "termvector": [
        "Term vector field-name mapping is built in index/upsidedown/upsidedown.go termVectorsFromTokenFreq; use .agent/smoke_term_vector_locations.sh.",
    ],
    "locations": [
        "Hit Locations are assembled in search/search.go, but term-vector field names are encoded in index/upsidedown/upsidedown.go termVectorsFromTokenFreq. Use .agent/smoke_term_vector_locations.sh when the report mentions empty field names.",
    ],
    "boltdb": [
        "Bolt store behavior is under index/upsidedown/store/boltdb/; use .agent/smoke_boltdb_open.sh for open/init panics and compare prefix Seek only for iterator bugs.",
    ],
    "cjk": [
        "CJK width voiced-mark bugs are usually in analysis/lang/cjk/cjk_width.go combine(); use .agent/smoke_cjk_width.sh.",
    ],
    "collector": [
        "Collector bugs split by path: heap/size-limit behavior is search/collector/heap.go and .agent/smoke_heap_collector.sh; ExternalID/fixup behavior is search/collector/topn.go and usually only needs .agent/validate_changed.sh.",
    ],
    "disjunction": [
        "Zero-result OR/search reports usually mean search/searcher/search_disjunction_slice.go before query validation; validate public match and OR behavior with .agent/smoke_disjunction_search.sh.",
    ],
    "disjunctionslicesearcher": [
        "DisjunctionSliceSearcher iteration lives in search/searcher/search_disjunction_slice.go; use .agent/smoke_disjunction_search.sh before building custom repros.",
    ],
    "sort": [
        "Sort panics involving SortOrder.Compare and TopN often involve score sorts. Score values are cached on DocumentMatch.Score, while DocumentMatch.Sort holds non-score sort keys; validate score+field sort and SearchAfter with .agent/smoke_sort_score_field.sh.",
    ],
    "topn": [
        "TopN custom-sort panics usually cross search/collector/topn.go and search/sort.go. For score+field sorts, compare cached score handling against non-score Sort indexes and use .agent/smoke_sort_score_field.sh.",
    ],
    "externalid": [
        "TopN ExternalID/fixup error handling is in search/collector/topn.go; .agent/smoke_heap_collector.sh is only for heap size-limit bugs.",
    ],
    "extractgeopoint": [
        "ExtractGeoPoint parsing and success booleans are in geo/parse.go; use .agent/smoke_extract_geopoint.sh, not the GeoPointField Analyze smoke.",
    ],
    "extractcircle": [
        "ExtractCircle map/string parsing is in geo/parse.go; use .agent/smoke_extract_circle.sh.",
    ],
    "fuzzy": [
        "Fuzzy search routing is search/query/fuzzy.go -> search/searcher/search_fuzzy.go; candidate enumeration and prefix handling live in NewFuzzySearcher, while scoring uses search/searcher/search_disjunction.go and search/levenshtein.go.",
    ],
    "conjunction": [
        "Conjunction push-down optimization is in search_conjunction.go; shared optimizeCompositeSearcher lives in search_disjunction.go. Use .agent/smoke_conjunction.sh for nil/empty optimization panics.",
    ],
    "phrase": [
        "Phrase path matching is in search/searcher/search_phrase.go findPhrasePaths(); use .agent/smoke_phrase_paths.sh for the base-case slice-bound panic.",
    ],
    "stempel": [
        "Stempel trie traversal is in analysis/lang/pl/stempel/trie.go; row getRef/getCmd helpers live in analysis/lang/pl/stempel/row.go. Use .agent/smoke_stempel_trie.sh.",
    ],
    "nextonly": [
        "UpsideDownCouchDocIDReader.nextOnly is in index/upsidedown/reader.go; use .agent/smoke_docid_reader.sh.",
    ],
    "docidreader": [
        "UpsideDownCouchDocIDReader.nextOnly is in index/upsidedown/reader.go; use .agent/smoke_docid_reader.sh.",
    ],
    "fragmenter": [
        "Simple highlighter fragments live in search/highlight/fragmenter/simple/simple.go; use .agent/smoke_highlight_fragmenter.sh.",
    ],
    "highlight": [
        "Highlight registry bugs live under registry/highlight.go; fragment contents live under search/highlight/fragmenter/. Use .agent/smoke_highlight_fragmenter.sh for empty fragment reports.",
    ],
    "exception": [
        "Exception tokenizer construction is in analysis/tokenizer/exception/exception.go.",
    ],
    "metrics": [
        "Metrics store error queue behavior is under index/upsidedown/store/metrics/.",
    ],
    "moss": [
        "Moss-backed upsidedown store code is under index/upsidedown/store/moss/.",
    ],
    "termfieldreader": [
        "Scorch TermFieldReader allocation/reuse lives in index/scorch/snapshot_index.go; use .agent/smoke_scorch_termreader.sh.",
    ],
    "geopoint": [
        "GeoPointField Analyze nil spatial plugin bugs are in document/field_geopoint.go; use .agent/smoke_geopoint_analyze.sh.",
    ],
    "geopointfield": [
        "GeoPointField Analyze nil spatial plugin bugs are in document/field_geopoint.go; use .agent/smoke_geopoint_analyze.sh.",
    ],
    "timestamp": [
        "Unix seconds timestamp parsing is in analysis/datetime/timestamp/seconds/seconds.go; use .agent/smoke_timestamp_seconds.sh.",
    ],
    "numericrangequery": [
        "NumericRangeQuery empty-field fallback is in search/query/numeric_range.go Searcher(); compare DateRangeQuery/TermRangeQuery for the default-field pattern before building a full repro.",
    ],
    "termrange": [
        "TermRange optimization errors usually route through search/searcher/search_term_range.go -> NewMultiTermSearcher -> search_disjunction.go optimizeCompositeSearcher.",
        "If the report says optimization context is skipped or unable to optimize, inspect optimizeCompositeSearcher before building a full index repro; the key invariant is when nil OptimizableContext should stop the composite.",
    ],
    "termrangequery": [
        "TermRangeQuery parsing/building is in search/query/term_range.go; execution/optimization is in search/searcher/search_term_range.go and search_disjunction.go.",
    ],
    "datetime": [
        "If the report is about stored DateTime field formatting or SearchRequest.Fields output, start in index_impl.go LoadAndHighlightFields; mapping/field.go creates fields but does not format search hit values.",
        "Empty DateFormat means RFC3339 fallback; named timestamp layouts are seconds/milliseconds/microseconds/nanoseconds. Use .agent/smoke_datetime_empty_layout.sh after editing.",
    ],
    "datetimefield": [
        "Stored DateTime field formatting for SearchRequest.Fields is in index_impl.go LoadAndHighlightFields, while document/field_datetime.go only returns the time/layout pair.",
        "Empty DateFormat means RFC3339 fallback; named timestamp layouts are seconds/milliseconds/microseconds/nanoseconds.",
    ],
    "thesaurus": [
        "ThesaurusKeys snapshot handling is in index/scorch/snapshot_index.go newIndexSnapshotThesaurusKeys.",
        "Compare both branches: the goroutine sending asynchSegmentResult and the result loop consuming it. A public bleve.NewMemOnly repro is awkward because Advanced() returns the generic index.Index interface.",
    ],
    "thesauruskeys": [
        "ThesaurusKeys snapshot handling is in index/scorch/snapshot_index.go newIndexSnapshotThesaurusKeys.",
        "Compare both branches: the goroutine sending asynchSegmentResult and the result loop consuming it. A public bleve.NewMemOnly repro is awkward because Advanced() returns the generic index.Index interface.",
    ],
    "getfieldname": [
        "Custom field-name resolution is mapping/field.go getFieldName(); check both the custom-name condition and parent path slicing.",
    ],
    "sqrtcache": [
        "Term frequency sqrt caching is in search/scorer/scorer_term.go; Freq < MaxSqrtCache uses SqrtCache, larger frequencies use math.Sqrt directly.",
    ],
    "maxsqrtcache": [
        "Term frequency sqrt caching is in search/scorer/scorer_term.go; Freq < MaxSqrtCache uses SqrtCache, larger frequencies use math.Sqrt directly.",
    ],
    "synonym": [
        "Synonym pre-search result merging is in pre_search.go; index_alias_impl.go only transports SynonymResult between indexes.",
        "SynonymSourceConstructor analyzer lookup lives in mapping/synonym.go; registry files only declare constructors.",
    ],
    "currmust": [
        "PhraseSearcher currMust panics usually live in search/searcher/search_phrase.go Advance(), not findPhrasePaths().",
    ],
    "backindexrow": [
        "BackIndexRow protobuf parsing lives in index/upsidedown/row.go visitBackIndexRowFieldTerms; validate valid rows and malformed byte handling with .agent/smoke_backindex_protobuf.sh.",
    ],
    "visitbackindexrowfieldterms": [
        "visitBackIndexRowFieldTerms is hand-copied protobuf parsing in index/upsidedown/row.go. Check wire type masking, varint accumulation, EOF bounds, and string length loop termination; use .agent/smoke_backindex_protobuf.sh.",
    ],
    "reverse": [
        "Reverse token filter Unicode handling is in analysis/token/reverse/reverse.go; combining marks should stay attached to their base rune when reversing.",
    ],
    "regexp": [
        "RegexpTokenizer token boundaries live in analysis/tokenizer/regexp/regexp.go; match length should use end-start, especially for matches starting at byte 0. Use .agent/smoke_regexp_tokenizer.sh.",
    ],
    "camelcase": [
        "CamelCase token splitting lives in analysis/token/camelcase/camelcase.go; check rune boundary indexes before changing offsets. Use .agent/smoke_camelcase.sh.",
    ],
    "booleanfield": [
        "BooleanField storage and Boolean() decoding live in document/field_boolean.go; a valid stored boolean is one byte. Use .agent/smoke_boolean_field.sh.",
    ],
    "iso": [
        "ISO datetime layout conversion lives under analysis/datetime/iso; parser progress bugs often come from advancing the wrong operator in token loops.",
    ],
    "indexalias": [
        "Empty IndexAlias behavior lives in index_alias_impl.go; operations must handle zero underlying indexes without indexing aliases[0].",
    ],
    "synonymsourceconstructor": [
        "SynonymSourceConstructor analyzer lookup lives in mapping/synonym.go; cache.AnalyzerNamed returning nil error means the analyzer exists.",
    ],
}

SMOKES = {
    "float64toint64": [".agent/smoke_numeric_float.sh"],
    "int64tofloat64": [".agent/smoke_numeric_float.sh"],
    "float": [".agent/smoke_numeric_float.sh"],
    "fielddescribedbypath": [".agent/smoke_field_mapping_lookup.sh"],
    "fieldmappingforpath": [".agent/smoke_field_mapping_lookup.sh"],
    "property": [".agent/smoke_field_mapping_lookup.sh"],
    "mapping": [".agent/smoke_mapping_path.sh", ".agent/smoke_field_mapping_lookup.sh"],
    "termvector": [".agent/smoke_term_vector_locations.sh"],
    "locations": [".agent/smoke_term_vector_locations.sh"],
    "dictionary": [".agent/smoke_dictionary_row.sh"],
    "nextonly": [".agent/smoke_docid_reader.sh"],
    "docidreader": [".agent/smoke_docid_reader.sh"],
    "extractcircle": [".agent/smoke_extract_circle.sh"],
    "fragmenter": [".agent/smoke_highlight_fragmenter.sh"],
    "highlight": [".agent/smoke_highlight_fragmenter.sh"],
    "datetimefield": [".agent/smoke_datetime_empty_layout.sh"],
    "getfieldname": [".agent/smoke_field_custom_name.sh"],
    "sqrtcache": [".agent/smoke_sqrt_cache.sh"],
    "maxsqrtcache": [".agent/smoke_sqrt_cache.sh"],
    "currmust": [".agent/smoke_phrase_advance_nil.sh"],
    "addnotexceedingsize": [".agent/smoke_collector_size_limit.sh"],
    "sort": [".agent/smoke_sort_score_field.sh"],
    "topn": [".agent/smoke_sort_score_field.sh"],
    "backindexrow": [".agent/smoke_backindex_protobuf.sh"],
    "visitbackindexrowfieldterms": [".agent/smoke_backindex_protobuf.sh"],
    "disjunction": [".agent/smoke_disjunction_search.sh"],
    "disjunctionslicesearcher": [".agent/smoke_disjunction_search.sh"],
    "regexp": [".agent/smoke_regexp_tokenizer.sh"],
    "camelcase": [".agent/smoke_camelcase.sh"],
    "booleanfield": [".agent/smoke_boolean_field.sh"],
}


def go_files() -> list[Path]:
    ignored = {".git", "vendor"}
    out: list[Path] = []
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".claude")]
        for name in files:
            if name.endswith(".go") and not name.endswith("_test.go"):
                out.append(Path(root, name))
    return out


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def tokens(query: str) -> list[str]:
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)*(?:/[0-9]+)?", query)
    parts: list[str] = []
    for item in raw:
        parts.append(item)
        parts.extend(re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)", item))
    seen = set()
    result = []
    for item in parts:
        low = item.lower()
        if len(low) < 2 or low in STOP or low in seen:
            continue
        seen.add(low)
        result.append(item)
    return result


def pkg_for(path: str) -> str:
    d = os.path.dirname(path) or "."
    return "." if d == "." else "./" + d


def first_matches(text: str, terms: list[str], limit: int = 5) -> list[str]:
    lines = text.splitlines()
    out = []
    lowered = [(t, t.lower()) for t in terms]
    for i, line in enumerate(lines, 1):
        low = line.lower()
        if any(tlow in low for _, tlow in lowered):
            out.append(f"{i}: {line.strip()[:180]}")
            if len(out) >= limit:
                break
    return out


def decl_matches(text: str, terms: list[str], limit: int = 5) -> list[str]:
    out = []
    wanted = [t.lower() for t in terms if len(t) >= 4]
    decl = re.compile(r"^\s*(func|type)\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)", re.M)
    for m in decl.finditer(text):
        name = m.group(2)
        low = name.lower()
        if any(w in low or low in w for w in wanted):
            line = text.count("\n", 0, m.start()) + 1
            out.append(f"{line}: {m.group(0).strip()}")
            if len(out) >= limit:
                break
    return out


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()
    if not query:
        print("usage: python3 .agent/bleve_triage.py 'exact report words or symbols'", file=sys.stderr)
        return 2

    terms = tokens(query)
    lows = [t.lower() for t in terms]
    files = go_files()
    scores: dict[str, int] = defaultdict(int)
    evidence: dict[str, list[str]] = {}

    for low in lows:
        for hint, paths in HINTS.items():
            if low == "extractgeopoint" and hint == "geopoint":
                continue
            if hint in low or low in hint:
                for p in paths:
                    for f in files:
                        r = rel(f)
                        if r == p.rstrip("/") or r.startswith(p):
                            scores[r] += 28 if r == p else 16

    qlow = query.lower()
    phrase_boosts = []
    if "geoshape" in qlow and any(w in qlow for w in ("zero", "no result", "match", "intersect", "contain", "within")):
        phrase_boosts.extend([
            ("search/searcher/search_geoshape.go", 70),
            ("search/searcher/", 20),
        ])
    if "geoshape" in qlow and any(w in qlow for w in ("create", "field", "circle", "shape creation")):
        phrase_boosts.extend([
            ("mapping/field.go", 80),
            ("document/field_geoshape.go", 45),
            ("geo/parse.go", 25),
        ])
    if "heap" in qlow or "topn" in qlow or "size limit" in qlow:
        phrase_boosts.extend([
            ("search/collector/slice.go", 95),
            ("search/collector/heap.go", 80),
            ("search/collector/topn.go", 35),
        ])
    if "custom sort" in qlow or ("sort" in qlow and ("topn" in qlow or "index out of range" in qlow or "cached scoring" in qlow)):
        phrase_boosts.extend([
            ("search/sort.go", 180),
            ("search/collector/topn.go", 120),
        ])
    if "externalid" in qlow:
        phrase_boosts.extend([
            ("search/collector/topn.go", 90),
        ])
    if "fuzzy" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_fuzzy.go", 150),
            ("search/query/fuzzy.go", 80),
            ("search/levenshtein.go", 40),
            ("search/searcher/search_disjunction.go", 25),
        ])
    if "prefix" in qlow and "fuzzy" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_fuzzy.go", 120),
        ])
    if "cjk" in qlow or "voiced" in qlow or "half-voiced" in qlow or "width" in qlow:
        phrase_boosts.extend([
            ("analysis/lang/cjk/cjk_width.go", 90),
        ])
    if "phrase" in qlow or "findphrasepaths" in qlow or "slice bounds" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_phrase.go", 90),
        ])
    if "disjunctionslicesearcher" in qlow or ("disjunction" in qlow and ("zero" in qlow or "no results" in qlow or "returns no" in qlow)):
        phrase_boosts.extend([
            ("search/searcher/search_disjunction_slice.go", 180),
            ("search/searcher/search_disjunction.go", 65),
        ])
    if "currmust" in qlow or ("phrase" in qlow and "advance" in qlow):
        phrase_boosts.extend([
            ("search/searcher/search_phrase.go", 140),
        ])
    if "termfieldreader" in qlow or "postings" in qlow or "allocTermFieldReaderDicts".lower() in qlow:
        phrase_boosts.extend([
            ("index/scorch/snapshot_index.go", 90),
        ])
    if "numericrangequery" in qlow or "numeric range" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_numeric_range.go", 95),
            ("search/query/numeric_range.go", 70),
        ])
    if "nil filter" in qlow or "termrange.enumerate" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_numeric_range.go", 140),
        ])
    if "term range" in qlow or "termrange" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_disjunction.go", 95),
            ("search/searcher/search_term_range.go", 80),
            ("search/searcher/search_multi_term.go", 45),
            ("search/query/term_range.go", 35),
        ])
    if "optimization" in qlow and "term range" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_disjunction.go", 80),
        ])
    if "float64toint64" in qlow or "int64tofloat64" in qlow or ("negative" in qlow and "sort" in qlow and "float" in qlow):
        phrase_boosts.extend([
            ("numeric/float.go", 120),
        ])
    if "term vector" in qlow or ("locations" in qlow and "empty" in qlow and "field" in qlow):
        phrase_boosts.extend([
            ("index/upsidedown/upsidedown.go", 100),
            ("search/scorer/scorer_term.go", 35),
            ("search/search.go", 25),
        ])
    if "getfieldname" in qlow or ("custom" in qlow and "field" in qlow and "name" in qlow):
        phrase_boosts.extend([
            ("mapping/field.go", 140),
        ])
    if "fielddescribedbypath" in qlow or "field mapping" in qlow or ("property" in qlow and "path" in qlow):
        phrase_boosts.extend([
            ("mapping/document.go", 110),
            ("mapping/field.go", 80),
            ("mapping/index.go", 35),
        ])
    if "empty path" in qlow or "path elements" in qlow:
        phrase_boosts.extend([
            ("mapping/document.go", 110),
            ("mapping/reflect.go", 25),
        ])
    if "newdictionaryrowk" in qlow or ("dictionary" in qlow and "row" in qlow):
        phrase_boosts.extend([
            ("index/upsidedown/row.go", 120),
        ])
    if "visitbackindexrowfieldterms" in qlow or ("back index" in qlow and ("wire" in qlow or "protobuf" in qlow or "corrupt" in qlow or "parsing" in qlow)):
        phrase_boosts.extend([
            ("index/upsidedown/row.go", 170),
        ])
    if "protocol buffer" in qlow or "protobuf" in qlow or "wire type" in qlow:
        phrase_boosts.extend([
            ("index/upsidedown/row.go", 150),
        ])
    if "reverse token" in qlow or ("reverse" in qlow and "combining" in qlow):
        phrase_boosts.extend([
            ("analysis/token/reverse/reverse.go", 160),
        ])
    if "regexp" in qlow and "token" in qlow:
        phrase_boosts.extend([
            ("analysis/tokenizer/regexp/regexp.go", 150),
        ])
    if "camelcase" in qlow or "camel case" in qlow:
        phrase_boosts.extend([
            ("analysis/token/camelcase/camelcase.go", 150),
        ])
    if "booleanfield" in qlow or ("boolean" in qlow and "bytes" in qlow):
        phrase_boosts.extend([
            ("document/field_boolean.go", 150),
        ])
    if "iso" in qlow and "datetime" in qlow:
        phrase_boosts.extend([
            ("analysis/datetime/iso/", 150),
        ])
    if "empty alias" in qlow or ("index alias" in qlow and "empty" in qlow):
        phrase_boosts.extend([
            ("index_alias_impl.go", 150),
        ])
    if "synonymsourceconstructor" in qlow or ("synonym" in qlow and "analyzer" in qlow):
        phrase_boosts.extend([
            ("mapping/synonym.go", 150),
        ])
    if "getref" in qlow and "stempel" in qlow:
        phrase_boosts.extend([
            ("analysis/lang/pl/stempel/row.go", 140),
            ("analysis/lang/pl/stempel/trie.go", 30),
        ])
    if "nextonly" in qlow or "docidreader" in qlow or ("document id" in qlow and "reader" in qlow):
        phrase_boosts.extend([
            ("index/upsidedown/reader.go", 140),
            ("index/upsidedown/index_reader.go", 35),
        ])
    if "simple fragmenter" in qlow or "empty fragments" in qlow:
        phrase_boosts.extend([
            ("search/highlight/fragmenter/simple/simple.go", 120),
            ("search/highlight/highlighter/simple/highlighter_simple.go", 35),
        ])
    if "extractcircle" in qlow or "circle" in qlow:
        phrase_boosts.extend([
            ("geo/parse.go", 100),
        ])
    if "exceptionstokenizer" in qlow or ("exception" in qlow and "tokenizer" in qlow):
        phrase_boosts.extend([
            ("analysis/tokenizer/exception/exception.go", 100),
        ])
    if "highlighternamed" in qlow or ("nil highlighter" in qlow):
        phrase_boosts.extend([
            ("registry/highlight.go", 100),
            ("search/highlight/", 20),
        ])
    if "document id" in qlow or "empty id" in qlow or ("non-empty" in qlow and "id" in qlow):
        phrase_boosts.extend([
            ("index_impl.go", 90),
            ("index.go", 25),
        ])
    if "geopointfield" in qlow or "spatialplugin" in qlow:
        phrase_boosts.extend([
            ("document/field_geopoint.go", 90),
        ])
    if "query string" in qlow or ("lexer" in qlow and "query" in qlow):
        phrase_boosts.extend([
            ("search/query/query_string_lex.go", 70),
            ("search/query/", 15),
        ])
    if "score" in qlow or "normalization" in qlow or "query norm" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_boolean.go", 35),
            ("search/scorer/", 30),
        ])
    if "sqrtcache" in qlow or "maxsqrtcache" in qlow or ("term" in qlow and "freq" in qlow and "panic" in qlow):
        phrase_boosts.extend([
            ("search/scorer/scorer_term.go", 120),
            ("search/scorer/sqrt_cache.go", 60),
        ])
    if "datetime field" in qlow and ("format" in qlow or "layout" in qlow or "rfc3339" in qlow):
        phrase_boosts.extend([
            ("index_impl.go", 260),
            ("document/field_datetime.go", 35),
        ])
    if "empty layout" in qlow or ("rfc3339" in qlow and "field" in qlow):
        phrase_boosts.extend([
            ("index_impl.go", 220),
        ])
    if "synonym" in qlow and ("pre-search" in qlow or "result" in qlow or "processed" in qlow):
        phrase_boosts.extend([
            ("pre_search.go", 140),
            ("index_alias_impl.go", 35),
        ])
    if "thesaurus" in qlow or "thesauruskeys" in qlow:
        phrase_boosts.extend([
            ("index/scorch/snapshot_index.go", 180),
        ])
    if "score breakdown" in qlow or "retrieve" in qlow and "breakdown" in qlow or "disjunction" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_disjunction.go", 60),
            ("search/query/disjunction.go", 25),
        ])
    for p, boost in phrase_boosts:
        for f in files:
            r = rel(f)
            if r == p.rstrip("/") or r.startswith(p):
                scores[r] += boost

    for f in files:
        r = rel(f)
        rlow = r.lower()
        text = f.read_text(errors="ignore")
        tlow = text.lower()
        for term in lows:
            if term in rlow:
                scores[r] += 12
            count = tlow.count(term)
            if count:
                scores[r] += min(20, count * 2)
        decls = decl_matches(text, terms)
        if decls:
            scores[r] += 35 + 5 * len(decls)
            evidence[r] = decls
        else:
            matches = first_matches(text, terms)
            if matches:
                evidence[r] = matches

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    print("Bleve triage")
    print("query terms:", ", ".join(terms) if terms else "(none)")
    print()
    if not ranked:
        print("No strong file match. Try a function/type/error phrase from the report.")
        return 1

    pkgs = []
    for n, (path, score) in enumerate(ranked, 1):
        print(f"{n}. {path}  score={score}  package={pkg_for(path)}")
        for line in evidence.get(path, [])[:4]:
            print(f"   {line}")
        pkg = pkg_for(path)
        if pkg not in pkgs:
            pkgs.append(pkg)
    print()
    print("Validation candidates:")
    for pkg in pkgs[:4]:
        print(f"  go test {pkg}")
    print("  .agent/validate_changed.sh")

    smoke_cmds = []
    for low in lows:
        key = "termvector" if low == "term" and "vector" in qlow else low
        key = "fragmenter" if "fragment" in low else key
        for cmd in SMOKES.get(key, []):
            if cmd not in smoke_cmds:
                smoke_cmds.append(cmd)
    if "term vector" in qlow and ".agent/smoke_term_vector_locations.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_term_vector_locations.sh")
    if "empty path" in qlow and ".agent/smoke_mapping_path.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_mapping_path.sh")
    if "datetime field" in qlow and ("layout" in qlow or "format" in qlow) and ".agent/smoke_datetime_empty_layout.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_datetime_empty_layout.sh")
    if "size limit" in qlow and ".agent/smoke_collector_size_limit.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_collector_size_limit.sh")
    if "custom sort" in qlow or ("sort" in qlow and ("topn" in qlow or "cached scoring" in qlow or "index out of range" in qlow)):
        if ".agent/smoke_sort_score_field.sh" not in smoke_cmds:
            smoke_cmds.append(".agent/smoke_sort_score_field.sh")
    if "fuzzy" in qlow and "prefix" in qlow and ".agent/smoke_fuzzy_prefix.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_fuzzy_prefix.sh")
    if "fuzzy" in qlow and any(w in qlow for w in ("score", "scoring", "nan", "edit distance")) and ".agent/smoke_fuzzy_score.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_fuzzy_score.sh")
    if "disjunction" in qlow and ".agent/smoke_disjunction_search.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_disjunction_search.sh")
    if "regexp" in qlow and "token" in qlow and ".agent/smoke_regexp_tokenizer.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_regexp_tokenizer.sh")
    if ("camelcase" in qlow or "camel case" in qlow) and ".agent/smoke_camelcase.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_camelcase.sh")
    if ("booleanfield" in qlow or ("boolean" in qlow and "bytes" in qlow)) and ".agent/smoke_boolean_field.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_boolean_field.sh")
    if ("back index" in qlow or "visitbackindexrowfieldterms" in qlow or "protobuf" in qlow or "protocol buffer" in qlow) and ".agent/smoke_backindex_protobuf.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_backindex_protobuf.sh")
    if "nil filter" in qlow and ".agent/smoke_numeric_range_nil_filter.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_numeric_range_nil_filter.sh")
    if "currmust" in qlow and ".agent/smoke_phrase_advance_nil.sh" not in smoke_cmds:
        smoke_cmds.append(".agent/smoke_phrase_advance_nil.sh")
    if smoke_cmds:
        print()
        print("Focused smoke helpers:")
        for cmd in smoke_cmds[:4]:
            print(f"  {cmd}")

    if "fuzzy" in qlow and "prefix" in qlow:
        print()
        print("fuzzy prefix note:")
        print("  - If prefix length is >= the query term length, clear/ignore the prefix constraint so normal fuzzy matching can include edit-distance matches with different prefixes; fixing byte-vs-rune counting alone is not enough for that report.")

    printed = set()
    for low in lows:
        key = "geoshape" if low.startswith("geo") and "shape" in low else low
        if key in API_NOTES and key not in printed:
            printed.add(key)
            print()
            print(f"{key} notes:")
            for note in API_NOTES[key]:
                print(f"  - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
