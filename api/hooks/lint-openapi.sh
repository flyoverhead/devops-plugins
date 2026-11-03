#!/bin/bash
file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$file" in
  *.yaml | *.yml | *.json) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0
grep -qE '^(openapi|swagger): |"(openapi|swagger)"[[:space:]]*:' "$file" || exit 0

if command -v spectral >/dev/null 2>&1; then
  args=()
  dir=$(dirname "$file")
  if ! compgen -G "$dir/.spectral.*" >/dev/null && ! compgen -G "./.spectral.*" >/dev/null; then
    args=(--ruleset "${CLAUDE_PLUGIN_ROOT}/skills/api-designer/assets/spectral.yaml")
  fi
  if ! out=$(spectral lint "$file" "${args[@]}" --format text 2>&1); then
    printf '%s\n' "$out" >&2
    exit 2
  fi
elif command -v redocly >/dev/null 2>&1; then
  if ! out=$(redocly lint "$file" 2>&1); then
    printf '%s\n' "$out" >&2
    exit 2
  fi
fi
exit 0
