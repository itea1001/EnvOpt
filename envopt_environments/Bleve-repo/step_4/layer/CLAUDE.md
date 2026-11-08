You are fixing one Bleve bug. Spend effort on the source bug, not repo discovery.

Fast path:
1. Start with one codebase-aware localization command, using 3-8 exact words or symbols from the report:
   `python3 .agent/bleve_triage.py 'GeoShape zero results intersects'`
   The tool ranks files, shows matching lines, prints focused smoke helpers when one matches, and prints the package test command. If its hints are weak, keep investigating normally.
2. Read narrow ranges around the ranked lines/functions. Prefer `Read` with `offset`/`limit` around the shown line numbers over whole-file reads, unless the file is small or the local context is still unclear.
3. Make the smallest source change that satisfies the report. Many failures here are inverted conditions, swapped branches, wrong comparison operators, or success/error checks in one local function.
4. Validate source changes with `.agent/validate_changed.sh`. It runs `go test` for every changed non-test Go package and exits nonzero on any failure. If triage or `.agent/bleve_map.md` names a focused `.agent/smoke_*.sh` helper for this subsystem, use it before inventing a `/tmp` repro. Current Bleve APIs: use `bleve.NewMemOnly`; `bleve.NewGeoShapeQuery` returns `(*GeoShapeQuery, error)`; mapping validation can use `IndexMapping.MapDocument`.
5. Final response: changed file, validation command, one-sentence rationale.

Useful navigation files:
- `.agent/bleve_map.md` has subsystem paths and package test guidance.
- `.agent/bleve_triage.py` is safe to rerun with better keywords when the first clue is too broad.

Validation notes:
- Do not treat a failing repro or test as success.
- Do not create temporary repro files in the repository when `/tmp` or a focused `.agent/smoke_*.sh` helper will do; repo-local scratch files make `validate_changed.sh` and `go test ./...` noisier.
- `search/sort.go` belongs to package `./search`, not `./search/sort`.
- If a focused repro fails after a plausible source edit, do not add unrelated source changes just to chase the repro. Recheck the repro setup against the local API and the source invariant first.
- If a `/tmp` repro fails to compile because of API uncertainty, prefer checking the relevant source/API docs and package tests rather than spending many turns repairing the repro.
- Broad validation is welcome when the change is broad or confidence is low; the helper is a starting point, not a ceiling.
