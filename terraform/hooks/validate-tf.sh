#!/usr/bin/env bash
set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v terraform >/dev/null 2>&1 || exit 0

file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$file" in
  */.terraform/*) exit 0 ;;
  *.tf) ;;
  *) exit 0 ;;
esac

[ -f "$file" ] || exit 0

dir=$(dirname "$file")
[ -d "$dir/.terraform" ] || exit 0

if ! out=$(cd "$dir" && terraform validate -no-color 2>&1); then
  printf '%s\n' "$out" >&2
  exit 2
fi
exit 0
