#!/usr/bin/env bash
set -u

command -v go >/dev/null 2>&1 || exit 0
version=$(go version 2>/dev/null) || exit 0
[ -n "$version" ] || exit 0

goroot=$(go env GOROOT 2>/dev/null)
gopath=$(go env GOPATH 2>/dev/null)
text="Go toolchain: ${version}; GOROOT=${goroot}; GOPATH=${gopath}"

if command -v jq >/dev/null 2>&1; then
  jq -cn --arg ctx "$text" \
    '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
else
  esc=${text//\\/\\\\}
  esc=${esc//\"/\\\"}
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$esc"
fi
exit 0
