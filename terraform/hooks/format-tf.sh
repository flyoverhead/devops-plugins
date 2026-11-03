#!/usr/bin/env bash
set -u

command -v jq >/dev/null 2>&1 || exit 0
command -v terraform >/dev/null 2>&1 || exit 0

file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$file" in
  */.terraform/*) exit 0 ;;
  *.tf | *.tfvars) ;;
  *) exit 0 ;;
esac

[ -f "$file" ] || exit 0

terraform fmt "$file" || true
exit 0
