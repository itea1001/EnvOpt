You are fixing one Bleve bug. Optimize for a minimal correct source patch with very few tool calls.

Required workflow:
1. Localize first. Extract function, type, package, error text, or field names from the report and run one targeted `rg -n` over `*.go`. Read only the nearest relevant ranges.
2. Treat the report as a strong hint. These failures are often one bad boolean/operator/branch/bounds condition near the named code. Check the local invariant before broad exploration.
3. Make the smallest source edit that restores every behavior named in the report. "Smallest" must not mean incomplete: if the report lists multiple invalid cases, input classes, or nil/non-nil paths, cover all of them in the local fix. If prose and repro details disagree, satisfy the explicit expected output/assertions from the repro.
4. Validate once with the narrowest useful command. Prefer `go test ./<changed-package>` or, if you have not already run that package, `.agent/test_changed.sh`. Do not run `go test ./...`; use `go build ./<changed-package>` if package tests are absent or unrelated.
5. Stop after one passing focused validation and a clean minimal diff. Final response: changed file, validation command, one-sentence rationale.

Cost controls:
- Do not create permanent `_test.go` files unless explicitly asked; hidden tests grade the source fix and this harness ignores test diffs.
- Do not create repo-root repro programs. If a repro is truly needed, use `/tmp` and delete it.
- If a direct report-matched operator/branch fix passes the changed package test, do not write a separate repro program just to re-prove the report.
- Do not repeat a command that already passed. Do not run broad `find`/`grep` sweeps after a named symbol has been found.
- If localization is unclear after two targeted searches, read `.agent/bleve_map.md` and then continue with package-local inspection.
- Keep reasoning and summaries concise. Use tools for evidence, not for ceremony.
