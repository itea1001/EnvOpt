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
    "addnotexceedingsize": ["search/collector/heap.go"],
    "backindex": ["index/upsidedown/back_index.go", "index/upsidedown/upsidedown.go"],
    "back": ["index/upsidedown/"],
    "booleanquery": ["search/query/boolean.go"],
    "boolean": ["search/query/boolean.go", "search/searcher/search_boolean.go"],
    "boltdb": ["index/upsidedown/store/boltdb/"],
    "bolt": ["index/upsidedown/store/boltdb/"],
    "cidr": ["search/query/ip_range.go", "search/searcher/search_ip_range.go", "document/field_ip.go"],
    "cjk": ["analysis/lang/cjk/cjk_width.go", "analysis/lang/cjk/"],
    "collector": ["search/collector/"],
    "conjunction": ["search/searcher/search_conjunction.go"],
    "dictionary": ["index/scorch/snapshot_index_dict.go", "index_impl.go", "index_alias_impl.go"],
    "dict": ["index/scorch/snapshot_index_dict.go"],
    "disjunction": ["search/searcher/search_disjunction.go", "search/query/disjunction.go"],
    "datetimeparsernamed": ["mapping/index.go"],
    "externalid": ["search/collector/topn.go"],
    "extractgeopoint": ["geo/parse.go"],
    "fieldcache": ["index/scorch/field_cache.go"],
    "findphrasepaths": ["search/searcher/search_phrase.go"],
    "forcemerge": ["index/scorch/scorch.go", "index/scorch/mergeplan/"],
    "geoboundingbox": ["search/searcher/search_geoboundingbox.go"],
    "geohash": ["geo/geohash.go"],
    "geopoint": ["document/field_geopoint.go", "search/searcher/search_geopointdistance.go"],
    "geopointfield": ["document/field_geopoint.go"],
    "geoshape": ["mapping/field.go", "search/searcher/search_geoshape.go", "search/query/geo_shape.go", "document/field_geoshape.go", "geo/"],
    "geojson": ["geo/parse.go", "document/field_geoshape.go", "search/searcher/search_geoshape.go"],
    "heap": ["search/collector/heap.go"],
    "iprange": ["search/query/ip_range.go", "search/searcher/search_ip_range.go"],
    "ip": ["search/query/ip_range.go", "search/searcher/search_ip_range.go", "document/field_ip.go", "mapping/field.go"],
    "iterator": ["index/upsidedown/store/", "index/scorch/snapshot_index_dict.go"],
    "levenshtein": ["search/levenshtein.go"],
    "marshal": ["index/upsidedown/"],
    "marshaling": ["index/upsidedown/"],
    "portuguese": ["analysis/lang/pt/"],
    "prefix": ["index/upsidedown/store/", "search/searcher/search_term_prefix.go"],
    "phrase": ["search/searcher/search_phrase.go", "search/query/phrase.go"],
    "postings": ["index/scorch/snapshot_index.go"],
    "numericrangequery": ["search/query/numeric_range.go"],
    "score": ["search/scorer/", "search/searcher/", "search/query/"],
    "snapshot": ["index/scorch/"],
    "stempel": ["analysis/lang/pl/stempel/"],
    "stemmer": ["analysis/lang/"],
    "termfieldreader": ["index/scorch/snapshot_index.go", "index/upsidedown/reader.go"],
    "topncollector": ["search/collector/topn.go", "search/collector/heap.go"],
    "upsidedown": ["index/upsidedown/"],
    "width": ["analysis/lang/cjk/cjk_width.go"],
}

API_NOTES = {
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
    "externalid": [
        "TopN ExternalID/fixup error handling is in search/collector/topn.go; .agent/smoke_heap_collector.sh is only for heap size-limit bugs.",
    ],
    "extractgeopoint": [
        "ExtractGeoPoint parsing and success booleans are in geo/parse.go; use .agent/smoke_extract_geopoint.sh, not the GeoPointField Analyze smoke.",
    ],
    "conjunction": [
        "Conjunction push-down optimization is in search_conjunction.go; shared optimizeCompositeSearcher lives in search_disjunction.go. Use .agent/smoke_conjunction.sh for nil/empty optimization panics.",
    ],
    "phrase": [
        "Phrase path matching is in search/searcher/search_phrase.go findPhrasePaths(); use .agent/smoke_phrase_paths.sh for the base-case slice-bound panic.",
    ],
    "stempel": [
        "Stempel trie traversal is in analysis/lang/pl/stempel/trie.go with row/cell helpers nearby; use .agent/smoke_stempel_trie.sh.",
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
            ("search/collector/heap.go", 80),
            ("search/collector/topn.go", 35),
        ])
    if "externalid" in qlow:
        phrase_boosts.extend([
            ("search/collector/topn.go", 90),
        ])
    if "cjk" in qlow or "voiced" in qlow or "half-voiced" in qlow or "width" in qlow:
        phrase_boosts.extend([
            ("analysis/lang/cjk/cjk_width.go", 90),
        ])
    if "phrase" in qlow or "findphrasepaths" in qlow or "slice bounds" in qlow:
        phrase_boosts.extend([
            ("search/searcher/search_phrase.go", 90),
        ])
    if "termfieldreader" in qlow or "postings" in qlow or "allocTermFieldReaderDicts".lower() in qlow:
        phrase_boosts.extend([
            ("index/scorch/snapshot_index.go", 90),
        ])
    if "numericrangequery" in qlow or "numeric range" in qlow:
        phrase_boosts.extend([
            ("search/query/numeric_range.go", 90),
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
