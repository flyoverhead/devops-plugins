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
  */.git/* | */.github/* | .github/* | */.venv/* | */.cache/* | */molecule/*) exit 0 ;;
esac
[ -f "$file" ] || exit 0
command -v ansible-lint >/dev/null 2>&1 || exit 0

is_ansible=0
case "$file" in
  */tasks/* | */handlers/* | */defaults/* | */vars/* | */meta/* | */playbooks/*) is_ansible=1 ;;
esac
if [ "$is_ansible" -eq 0 ]; then
  dir=$(dirname "$file")
  for _ in 1 2 3 4 5; do
    if [ -d "$dir/tasks" ] || [ -d "$dir/handlers" ] || [ -d "$dir/defaults" ] || [ -d "$dir/roles" ] \
      || [ -f "$dir/site.yml" ] || [ -f "$dir/playbook.yml" ]; then
      is_ansible=1
      break
    fi
    parent=$(dirname "$dir")
    [ "$parent" = "$dir" ] && break
    dir=$parent
  done
fi
[ "$is_ansible" -eq 1 ] || exit 0

project="${CLAUDE_PROJECT_DIR:-$PWD}"
case "$file" in
  /*) target=$file ;;
  *) target="$PWD/$file" ;;
esac
cd "$project" 2>/dev/null || exit 0

if [ -f "$project/.ansible-lint" ]; then
  out=$(ansible-lint --nocolor -c "$project/.ansible-lint" "$target" 2>&1)
else
  out=$(ansible-lint --nocolor --profile production "$target" 2>&1)
fi
rc=$?

if [ "$rc" -ne 0 ]; then
  printf 'ansible-lint findings in %s:\n%s\n' "$file" "$out" >&2
  exit 2
fi
exit 0
