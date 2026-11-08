#!/usr/bin/env bash
set -euo pipefail

test_file="mapping/zz_agent_field_custom_name_test.go"
trap 'rm -f "$test_file"' EXIT
cat > "$test_file" <<'GO'
package mapping

import "testing"

func TestAgentGetFieldNameCustomParentPathSmoke(t *testing.T) {
	fm := &FieldMapping{Name: "custom_field"}
	got := getFieldName("parent.field", []string{"parent", "field"}, fm)
	if got != "parent.custom_field" {
		t.Fatalf("getFieldName custom parent path=%q want %q", got, "parent.custom_field")
	}
}
GO

go test ./mapping -run TestAgentGetFieldNameCustomParentPathSmoke -count=1
