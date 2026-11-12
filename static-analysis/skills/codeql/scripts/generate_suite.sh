#!/usr/bin/env bash
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)

usage() {
  echo "usage: CODEQL_LANG=<lang> OUTPUT_DIR=<dir> [INSTALLED_THIRD_PARTY_PACKS='a/b c/d'] generate_suite.sh run-all|important-only"
}

MODE="${1:-}"
case "$MODE" in
  run-all|important-only) ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
: "${CODEQL_LANG:?set CODEQL_LANG (go, python, javascript, java, cpp, csharp, ruby, swift, rust)}"
: "${OUTPUT_DIR:?set OUTPUT_DIR}"
case "$CODEQL_LANG" in
  go|python|javascript|java|cpp|csharp|ruby|swift|rust) ;;
  *) echo "generate_suite.sh: unsupported CODEQL_LANG: $CODEQL_LANG" >&2; exit 1 ;;
esac

REQUESTED=()
read -r -a REQUESTED <<< "${INSTALLED_THIRD_PARTY_PACKS:-}"
PACKS=()
for spec in ${REQUESTED[@]+"${REQUESTED[@]}"}; do
  case "${spec%%@*}" in
    */*/*|/*|*/) bad=1 ;;
    */*) bad=0 ;;
    *) bad=1 ;;
  esac
  if [ "$bad" = 1 ] || printf '%s' "${spec%%@*}" | grep -q '[^A-Za-z0-9_/-]'; then
    echo "generate_suite.sh: INSTALLED_THIRD_PARTY_PACKS holds '$spec', which is not <scope>/<name>[@version]" >&2
    exit 1
  fi
  PACKS+=("${spec%%@*}")
done

mkdir -p "$OUTPUT_DIR/raw" || exit 1
SUITE="$OUTPUT_DIR/raw/$MODE.qls"
L="$CODEQL_LANG"

select_from() { printf -- '- {queries: ., from: %s}\n' "$1"; }
import_suite() { printf -- '- {import: codeql-suites/%s-%s.qls, from: codeql/%s-queries}\n' "$L" "$1" "$L"; }
keep_kinds() { printf -- '- include: {kind: [problem, path-problem]%s}\n' "$1"; }

write_suite() {
  printf -- '- description: %s suite for %s\n' "$MODE" "$L"
  case "$MODE" in
    run-all)
      import_suite security-and-quality
      import_suite security-experimental ;;
    important-only)
      select_from "codeql/$L-queries" ;;
  esac
  for pack in ${PACKS[@]+"${PACKS[@]}"}; do select_from "$pack"; done
  case "$MODE" in
    run-all)
      keep_kinds '' ;;
    important-only)
      keep_kinds ', tags contain: security, precision: [high, very-high]'
      keep_kinds ', tags contain: security, precision: medium' ;;
  esac
  printf -- '- exclude: {deprecated: //}\n'
  printf -- '- exclude: {tags contain: [modeleditor, modelgenerator]}\n'
}
write_suite > "$SUITE" || exit 1

if ! python3 "$HERE/verify_query_suite.py" "$SUITE"; then
  rm -f "$SUITE"
  echo "generate_suite.sh: $SUITE resolved no queries and was removed" >&2
  exit 1
fi
echo "$SUITE"
