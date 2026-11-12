#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module example.com/pinger

go 1.22
' > go.mod
cat > main.go <<'GO'
package main

import (
	"net/http"
	"os/exec"
)

func pingHandler(rw http.ResponseWriter, req *http.Request) {
	host := req.URL.Query().Get("host")
	out, _ := exec.Command("sh", "-c", "ping -c 1 "+host).CombinedOutput()
	_, _ = rw.Write(out)
}

func main() {
	http.HandleFunc("/ping", pingHandler)
	_ = http.ListenAndServe(":8080", nil)
}
GO
cat > results.sarif <<'JSON'
{
  "version": "2.1.0",
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "CodeQL",
          "rules": [
            {
              "id": "go/command-injection",
              "name": "go/command-injection",
              "shortDescription": {"text": "Command built from user-controlled sources"},
              "defaultConfiguration": {"level": "error"},
              "properties": {"precision": "high", "security-severity": "9.8", "tags": ["security", "external/cwe/cwe-078"]}
            },
            {
              "id": "go/unhandled-writable-file-close",
              "name": "go/unhandled-writable-file-close",
              "shortDescription": {"text": "Ignored write result"},
              "defaultConfiguration": {"level": "warning"},
              "properties": {"precision": "medium", "tags": ["reliability"]}
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "go/command-injection",
          "ruleIndex": 0,
          "message": {"text": "Shell command assembled from the host query parameter."},
          "locations": [{"physicalLocation": {"artifactLocation": {"uri": "main.go", "uriBaseId": "%SRCROOT%"}, "region": {"startLine": 10, "startColumn": 12}}}],
          "partialFingerprints": {"primaryLocationLineHash": "a1b2c3d4e5f60718:1"}
        },
        {
          "ruleId": "go/unhandled-writable-file-close",
          "ruleIndex": 1,
          "message": {"text": "Write error is ignored."},
          "locations": [{"physicalLocation": {"artifactLocation": {"uri": "main.go", "uriBaseId": "%SRCROOT%"}, "region": {"startLine": 11, "startColumn": 2}}}],
          "partialFingerprints": {"primaryLocationLineHash": "0f1e2d3c4b5a6978:1"}
        }
      ]
    }
  ]
}
JSON
git add -A && git commit -q -m init
