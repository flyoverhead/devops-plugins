#!/usr/bin/env bash
set -uo pipefail

input=$(cat)
if command -v jq >/dev/null 2>&1; then
  file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
elif command -v python3 >/dev/null 2>&1; then
  file=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
else
  exit 0
fi

case "$file" in
  *.yml | *.yaml) ;;
  *) exit 0 ;;
esac
case "$file" in
  */.git/* | */.venv/* | */.cache/* | */molecule/*) exit 0 ;;
esac
[ -f "$file" ] || exit 0
command -v yamllint >/dev/null 2>&1 || exit 0

default_config='extends: default
rules:
  line-length:
    max: 160
  comments:
    min-spaces-from-content: 1
  comments-indentation: disable
  braces:
    max-spaces-inside: 1
  octal-values:
    forbid-implicit-octal: true
    forbid-explicit-octal: true
  document-start:
    present: true
    level: error
  truthy:
    allowed-values: ["true", "false"]
    check-keys: false
    level: error'

project_config="${CLAUDE_PROJECT_DIR:-.}/.yamllint"
if [ -f "$project_config" ]; then
  out=$(yamllint -c "$project_config" -f parsable "$file" 2>&1)
else
  out=$(yamllint -d "$default_config" -f parsable "$file" 2>&1)
fi
rc=$?

if [ "$rc" -ne 0 ]; then
  printf 'yamllint findings in %s:\n%s\n' "$file" "$out" >&2
  exit 2
fi
exit 0
