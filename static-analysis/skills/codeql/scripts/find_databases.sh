#!/usr/bin/env bash
# Callers must read this through command substitution and check $? (exit 2 = codeql missing, not "no database").
set -uo pipefail

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  echo "usage: find_databases.sh [ROOT...]"
  echo "Prints every CodeQL database under the roots (depth <= 3), one per line."
  echo "Default roots: \$OUTPUT_DIR if set, then \$TMPDIR/codeql-<repo>_* for the current repo."
  exit 0
fi

if ! command -v codeql >/dev/null 2>&1; then
  echo "find_databases.sh: codeql is not on PATH; cannot tell real databases from failed builds" >&2
  exit 2
fi

roots=()
if [ $# -gt 0 ]; then
  roots=("$@")
else
  [ -n "${OUTPUT_DIR:-}" ] && roots+=("$OUTPUT_DIR")
  top=$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)
  repo=$(basename "$top")
  for d in "${TMPDIR:-/tmp}"/codeql-"$repo"_*; do
    [ -d "$d" ] && roots+=("$d")
  done
fi

seen=$'\n'
for root in ${roots[@]+"${roots[@]}"}; do
  [ -d "$root" ] || continue
  while IFS= read -r -d '' marker; do
    db=$(cd -P "$(dirname "$marker")" 2>/dev/null && pwd -P) || continue
    case "$seen" in *$'\n'"$db"$'\n'*) continue ;; esac
    seen="$seen$db"$'\n'
    if codeql resolve database -- "$db" >/dev/null 2>&1; then
      printf '%s\n' "$db"
    fi
  done < <(find "$root" -maxdepth 3 \( ! -path "$root" -type d -name '.*' \) -prune \
             -o -type f -name codeql-database.yml -print0 2>/dev/null)
done
exit 0
