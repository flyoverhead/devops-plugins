#!/usr/bin/env bash
set -uo pipefail

command -v ansible >/dev/null 2>&1 || exit 0

version_info=$(ansible --version 2>/dev/null)
core=$(printf '%s\n' "$version_info" | sed -n '1s/.*core \([0-9][0-9.]*\).*/\1/p')
py=$(printf '%s\n' "$version_info" | sed -n 's/^ *python version = \([0-9][0-9.]*\).*/\1/p' | head -n 1)

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Ansible core %s, Python %s"}}\n' \
  "${core:-unknown}" "${py:-unknown}"
exit 0
