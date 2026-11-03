#!/bin/bash
found=()

version_of() {
  local v
  v=$("$1" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
  printf '%s' "${v:-?}"
}

for tool in spectral redocly; do
  command -v "$tool" >/dev/null 2>&1 && found+=("$tool@$(version_of "$tool")")
done
command -v swagger-cli >/dev/null 2>&1 && found+=("swagger-cli")

if [ "${#found[@]}" -gt 0 ]; then
  msg="OpenAPI tooling available: ${found[*]}"
else
  msg="No OpenAPI validators found; install spectral or redocly to lint specs."
fi

if command -v jq >/dev/null 2>&1; then
  jq -nc --arg msg "$msg" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $msg}}'
else
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
fi
exit 0
