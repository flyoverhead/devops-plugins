#!/usr/bin/env bash
set -u

command -v terraform >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

version=$(terraform version -json 2>/dev/null | jq -r '.terraform_version // empty' 2>/dev/null)
if [ -z "$version" ]; then
  version=$(terraform version 2>/dev/null | head -n 1 | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -n 1)
fi
[ -n "$version" ] || exit 0

text="Terraform ${version} is installed. This plugin blocks apply, destroy, import, taint and state mutation; read plan output before anyone applies it."

jq -n --arg text "$text" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $text}}'
exit 0
