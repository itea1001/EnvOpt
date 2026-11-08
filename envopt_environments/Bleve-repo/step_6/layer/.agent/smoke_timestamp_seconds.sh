#!/usr/bin/env bash
set -euo pipefail

prog="${TMPDIR:-/tmp}/bleve_timestamp_seconds_smoke.go"
cat > "$prog" <<'GO'
package main

import (
	"fmt"
	"os"
	"time"

	"github.com/blevesearch/bleve/v2/analysis/datetime/timestamp/seconds"
)

func main() {
	parser := &seconds.DateTimeParser{}
	tm, name, err := parser.ParseDateTime("1609459200")
	if err != nil || name != seconds.Name || !tm.Equal(time.Unix(1609459200, 0)) {
		fmt.Printf("valid timestamp parse got time=%v name=%q err=%v\n", tm, name, err)
		os.Exit(1)
	}
	if _, _, err := parser.ParseDateTime("not_a_number"); err == nil {
		fmt.Println("invalid timestamp parsed without error")
		os.Exit(1)
	}
	fmt.Println("timestamp seconds smoke passed")
}
GO

go run "$prog"
