#!/usr/bin/env bash
set -u

file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0

case "$file" in
  *.go) ;;
  *) exit 0 ;;
esac
case "$file" in
  */vendor/* | *.pb.go) exit 0 ;;
esac

command -v gofmt >/dev/null 2>&1 || exit 0
[ -f "$file" ] || exit 0

gofmt -w "$file" 2>&1
exit 0
