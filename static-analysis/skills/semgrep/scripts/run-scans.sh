#!/usr/bin/env bash
# Must stay bash 3.2 compatible (stock macOS): no associative arrays, no wait -n.
# No nounset: bash 3.2 treats "${empty[@]}" as unbound under -u.
set -o pipefail

ME=run-scans.sh

show_help() {
  cat <<'EOF'
Run an approved Semgrep plan and record every scan in scans.json.

Synopsis
  run-scans.sh --target DIR --output-dir DIR --mode MODE --rulesets FILE [options]

Required
  --target DIR          repository to scan; absolute path
  --output-dir DIR      where raw/, results/, repos/ and scans.json go; absolute path
  --mode MODE           run-all | important-only (important-only scans WARNING and ERROR rules only)
  --rulesets FILE       the approved plan, a JSON object of arrays:
                        baseline and <language> keys: registry ids (p/..., r/...)
                        third_party: https git URLs; local: absolute rule directories

Options
  --pro                 add --pro to every semgrep call (only on the user's say-so)
  --jobs N              semgrep processes at once; default 4
  --max-target-bytes N  semgrep skips larger files; default 20000000, 0 disables the limit
  --dry-run             print what would run; clone and scan nothing
  --help                this text

Exit status
  0  one or more scans succeeded; stdout is the path of scans.json
  1  bad arguments, bad plan, or every scan failed
EOF
}

fail() { printf '%s: %s\n' "$ME" "$*" >&2; exit 1; }
reject() { fail "$1: $2"; }

TARGET='' OUTPUT_DIR='' MODE='' RULESETS='' PRO=0 JOBS=4 MAX_BYTES=20000000 DRY_RUN=0
while [ $# -gt 0 ]; do
  opt=$1
  case "$opt" in
    --pro) PRO=1; shift; continue ;;
    --dry-run) DRY_RUN=1; shift; continue ;;
    -h|--help) show_help; exit 0 ;;
    --target|--output-dir|--mode|--rulesets|--jobs|--max-target-bytes) ;;
    *) reject "$opt" "unknown option" ;;
  esac
  [ $# -ge 2 ] || reject "$opt" "missing value"
  case "$opt" in
    --target) TARGET=$2 ;;
    --output-dir) OUTPUT_DIR=$2 ;;
    --mode) MODE=$2 ;;
    --rulesets) RULESETS=$2 ;;
    --jobs) JOBS=$2 ;;
    --max-target-bytes) MAX_BYTES=$2 ;;
  esac
  shift 2
done

unsafe_path() {
  case "$1" in *[\"\'\`\$\\]*) return 0 ;; esac
  printf '%s' "$1" | LC_ALL=C grep -q '[[:cntrl:]]'
}

validate_args() {
  local flag value
  for flag in --target --output-dir; do
    if [ "$flag" = --target ]; then value=$TARGET; else value=$OUTPUT_DIR; fi
    [ -n "$value" ] || reject "$flag" "required"
    [ "${value#/}" != "$value" ] || reject "$flag" "needs an absolute path, got '$value'"
    if unsafe_path "$value"; then reject "$flag" "quotes, \$, backslashes and control characters are refused"; fi
  done
  [ -d "$TARGET" ] || reject --target "no such directory: $TARGET"
  [ "$MODE" = run-all ] || [ "$MODE" = important-only ] || reject --mode "expected run-all or important-only, got '$MODE'"
  { [ -f "$RULESETS" ] && [ -r "$RULESETS" ]; } || reject --rulesets "cannot read '$RULESETS'"
  printf '%s' "$JOBS" | grep -Eq '^[0-9]+$' && [ "$JOBS" -gt 0 ] || reject --jobs "expected a whole number above zero, got '$JOBS'"
  printf '%s' "$MAX_BYTES" | grep -Eq '^[0-9]+$' || reject --max-target-bytes "expected plain digits (0 = unlimited), got '$MAX_BYTES'"
  command -v jq >/dev/null 2>&1 || fail "jq not found on PATH"
}
validate_args

# shellcheck disable=SC2016
PLAN_JQ='
def canon: ascii_downcase as $k
  | {js: "javascript", jsx: "javascript", node: "javascript", nodejs: "javascript",
     ts: "typescript", tsx: "typescript", golang: "go", py: "python", python3: "python",
     k8s: "kubernetes", tf: "terraform", hcl: "terraform", sh: "bash", shell: "bash",
     docker: "dockerfile", containerfile: "dockerfile", yml: "yaml", gha: "github-actions",
     github_actions: "github-actions", actions: "github-actions", cfn: "cloudformation",
     rb: "ruby", "c++": "cpp", cxx: "cpp", cs: "csharp", "c#": "csharp", dotnet: "csharp",
     kt: "kotlin", rs: "rust", sol: "solidity"}[$k] // $k;
def registry: test("^[pr]/[A-Za-z0-9][A-Za-z0-9._/-]*$");
def https_git: test("^https://[A-Za-z0-9.-]+(:[0-9]+)?/[A-Za-z0-9._~/-]+$");
if type != "object" or any(.[]; type != "array") then "ERR\tthe plan must be a JSON object whose values are arrays"
else to_entries[] | .key as $key | .value[]
  | if type != "string" then "ERR\t\($key): entries must be strings"
    elif $key == "third_party" then (if https_git then "clone\tall\t\(.)" else "ERR\tthird_party: \(.) is not an https git URL" end)
    elif $key == "local" then (if startswith("/") then "local\tall\t\(.)" else "ERR\tlocal: \(.) is not an absolute directory" end)
    elif registry | not then "ERR\t\($key): \(.) is not a registry id (p/... or r/...)"
    elif $key == "baseline" then "cross\tall\t\(.)"
    else "lang\t\($key | canon)\t\(.)" end
end'

PLAN_LINES=$(jq -r "$PLAN_JQ" "$RULESETS" 2>/dev/null) || fail "--rulesets: not valid JSON"
TAB=$(printf '\t')
plan_error=$(printf '%s\n' "$PLAN_LINES" | grep "^ERR$TAB" | head -n 1)
[ -z "$plan_error" ] || fail "${plan_error#ERR"$TAB"}"

TARGET_REAL=$(cd -P "$TARGET" && pwd -P) || fail "cannot resolve $TARGET"
[ "$DRY_RUN" = 1 ] || mkdir -p "$OUTPUT_DIR" || fail "cannot create $OUTPUT_DIR"
if [ -d "$OUTPUT_DIR" ]; then
  OUT_REAL=$(cd -P "$OUTPUT_DIR" && pwd -P) || fail "cannot resolve $OUTPUT_DIR"
else
  anchor=$OUTPUT_DIR
  until [ -d "$anchor" ]; do anchor=$(dirname "$anchor"); done
  OUT_REAL="$(cd -P "$anchor" && pwd -P)${OUTPUT_DIR#"$anchor"}"
fi
[ "$OUT_REAL" = "$TARGET_REAL" ] && reject --output-dir "must not be the target directory itself"

EXCLUDE_PATTERN=''
case "$OUT_REAL/" in "$TARGET_REAL"/*) EXCLUDE_PATTERN=${OUT_REAL#"$TARGET_REAL"/} ;; esac

RAW_DIR=$OUTPUT_DIR/raw
REPOS_DIR=$OUTPUT_DIR/repos
SCANS_JSON=$OUTPUT_DIR/scans.json

GLOB_TABLE='
go *.go
python *.py *.pyi
javascript *.js *.jsx *.mjs *.cjs
typescript *.ts *.tsx
bash *.sh *.bash
terraform *.tf *.tfvars *.hcl
dockerfile Dockerfile *.dockerfile
yaml *.yml *.yaml
github-actions *.yml *.yaml
kubernetes *.yml *.yaml
cloudformation *.yml *.yaml *.json
json *.json
ruby *.rb *.erb
java *.java
kotlin *.kt *.kts
php *.php
c *.c *.h
cpp *.cpp *.cc *.cxx *.hpp *.hh *.hxx *.h
csharp *.cs
rust *.rs
scala *.scala
swift *.swift
elixir *.ex *.exs
apex *.cls *.trigger
solidity *.sol
html *.html *.htm
'
globs_of() { printf '%s\n' "$GLOB_TABLE" | awk -v want="$1" '$1 == want { for (i = 2; i <= NF; i++) print $i }'; }

safe_name() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }
member() { local item=$1; shift; while [ $# -gt 0 ]; do [ "$1" = "$item" ] && return 0; shift; done; return 1; }

U_KIND=() U_LANG=() U_RULESET=() U_CONFIG=()
LANGS=() ALSO_SHARED=() UNSCOPED=() BASELINE=() CLONES_URL=() CLONES_DIR=()
add_unit() { U_KIND+=("$1"); U_LANG+=("$2"); U_RULESET+=("$3"); U_CONFIG+=("$4"); }

while IFS="$TAB" read -r kind lang item; do
  [ "$kind" = cross ] && ! member "$item" "${BASELINE[@]}" && BASELINE+=("$item")
done <<EOF
$PLAN_LINES
EOF

while IFS="$TAB" read -r kind lang item; do
  case "$kind" in
    lang)
      member "$lang" "${LANGS[@]}" || LANGS+=("$lang")
      if member "$item" "${BASELINE[@]}"; then
        member "$lang/$item" "${ALSO_SHARED[@]}" || ALSO_SHARED+=("$lang/$item")
        continue
      fi
      already=0
      for k in "${!U_RULESET[@]}"; do
        [ "${U_LANG[$k]}" = "$lang" ] && [ "${U_RULESET[$k]}" = "$item" ] && already=1
      done
      [ "$already" = 1 ] || add_unit lang "$lang" "$item" "$item" ;;
    cross)
      member "$item" "${U_RULESET[@]}" || add_unit cross all "$item" "$item" ;;
    clone)
      slug=${item#https://}; slug=${slug#*/}; slug=${slug%/}; slug=${slug%.git}
      dir="$(safe_name "${slug%%/*}")-$(safe_name "${slug##*/}")"
      member "$dir" "${CLONES_DIR[@]}" && continue
      CLONES_URL+=("$item"); CLONES_DIR+=("$dir")
      add_unit clone all "$item" "$REPOS_DIR/$dir" ;;
    local)
      member "$item" "${U_RULESET[@]}" && continue
      unsafe_path "$item" && fail "local: $item has quotes, \$, backslashes or control characters"
      [ -d "$item" ] || fail "local: no such directory: $item"
      [ -n "$(find "$item" -type f \( -name '*.yml' -o -name '*.yaml' \) -print -quit)" ] \
        || fail "local: $item holds no .yml/.yaml rule files"
      add_unit local all "$item" "$item" ;;
  esac
done <<EOF
$PLAN_LINES
EOF

for lang in "${LANGS[@]}"; do
  [ -n "$(globs_of "$lang")" ] || UNSCOPED+=("$lang")
done
[ ${#U_RULESET[@]} -gt 0 ] || fail "the plan yields no scans; is the rulesets file empty?"

U_STEM=()
for i in "${!U_RULESET[@]}"; do
  case "${U_KIND[$i]}" in
    clone) label=${U_CONFIG[$i]##*/} ;;
    local) label="local-$(basename "${U_CONFIG[$i]}")" ;;
    *) label=${U_RULESET[$i]} ;;
  esac
  base="${U_LANG[$i]}-$(safe_name "$label")" stem=$base suffix=1
  while member "$stem" "${U_STEM[@]}"; do suffix=$((suffix + 1)); stem="$base-$suffix"; done
  U_STEM+=("$stem")
done

semgrep_argv() {
  local i=$1 glob
  ARGV=(semgrep scan)
  if [ "$PRO" = 1 ]; then ARGV+=(--pro); fi
  ARGV+=(--metrics=off --disable-version-check "--max-target-bytes=$MAX_BYTES")
  if [ "$MODE" = important-only ]; then ARGV+=(--severity WARNING --severity ERROR); fi
  if [ "${U_KIND[$i]}" = lang ]; then
    while IFS= read -r glob; do ARGV+=("--include=$glob"); done < <(globs_of "${U_LANG[$i]}")
  fi
  if [ -n "$EXCLUDE_PATTERN" ]; then ARGV+=("--exclude=$EXCLUDE_PATTERN"); fi
  ARGV+=("--config=${U_CONFIG[$i]}")
  ARGV+=("--json-output=$RAW_DIR/${U_STEM[$i]}.json" "--sarif-output=$RAW_DIR/${U_STEM[$i]}.sarif" .)
}

if [ "$DRY_RUN" = 1 ]; then
  printf '# target: %s\n# output: %s (mode %s)\n' "$TARGET_REAL" "$OUTPUT_DIR" "$MODE"
  for i in "${!CLONES_URL[@]}"; do
    printf '%q ' git clone --quiet --depth=1 -- "${CLONES_URL[$i]}" "$REPOS_DIR/${CLONES_DIR[$i]}"; echo
  done
  for i in "${!U_RULESET[@]}"; do
    semgrep_argv "$i"
    printf '(cd %q && ' "$TARGET_REAL"; printf '%q ' "${ARGV[@]}"; echo ')'
  done
  for entry in "${ALSO_SHARED[@]}"; do echo "# alsoShared: $entry"; done
  for entry in "${UNSCOPED[@]}"; do echo "# unscoped: $entry"; done
  if [ -n "$EXCLUDE_PATTERN" ]; then echo "# excludePattern: $EXCLUDE_PATTERN"; fi
  exit 0
fi

command -v semgrep >/dev/null 2>&1 || fail "semgrep not found on PATH; install a pinned version yourself, this script never installs it"
version_text=$(semgrep --disable-version-check --version 2>&1)
if printf '%s' "$version_text" | grep -q 'no trust anchor'; then
  export SSL_CERT_FILE="${SEMGREP_FALLBACK_CA:-/etc/ssl/cert.pem}"
  printf '%s: no CA store in this sandbox; retrying with SSL_CERT_FILE=%s\n' "$ME" "$SSL_CERT_FILE" >&2
fi

[ -n "$RAW_DIR" ] && rm -rf "$RAW_DIR"
mkdir -p "$RAW_DIR" "$OUTPUT_DIR/results" || fail "cannot create $RAW_DIR"
SCRATCH=$(mktemp -d -t semgrep-runner.XXXXXXXX) || fail "cannot create a scratch directory"
trap '[ -n "$SCRATCH" ] && rm -rf "$SCRATCH"' EXIT
OK_LOG=$SCRATCH/ok.jsonl FAIL_LOG=$SCRATCH/failed.jsonl SKIP_LOG=$SCRATCH/skipped.jsonl
: > "$OK_LOG"; : > "$FAIL_LOG"; : > "$SKIP_LOG"

note_skip() { jq -cn --arg ruleset "$1" --arg reason "$2" '$ARGS.named' >> "$SKIP_LOG"; }

rule_files() { find "$1" -path "$1/.git" -prune -o -type f \( -name '*.yml' -o -name '*.yaml' \) "$2"; }
unloadable() {
  grep -Eq '^rules:' "$1" || return 0
  grep -Eq '^[[:space:]]*mode:[[:space:]]*join' "$1" && grep -Eq '^[[:space:]]*join:' "$1"
}

CLONED=()
for i in "${!CLONES_URL[@]}"; do
  url=${CLONES_URL[$i]} dest=$REPOS_DIR/${CLONES_DIR[$i]}
  mkdir -p "$REPOS_DIR"
  [ -n "${CLONES_DIR[$i]}" ] && rm -rf "$dest"
  if ! git clone --quiet --depth=1 -- "$url" "$dest" 2>"$SCRATCH/clone.err"; then
    note_skip "$url" "clone failed: $(tail -c 300 "$SCRATCH/clone.err")"
    continue
  fi
  removed=0 stuck=0
  while IFS= read -r -d '' rule; do
    unloadable "$rule" || continue
    if rm -f "$rule"; then removed=$((removed + 1)); else stuck=1; fi
  done < <(rule_files "$dest" -print0)
  if [ "$stuck" = 1 ]; then note_skip "$url" "could not prune unloadable rule files"; continue; fi
  printf '%s: %s: pruned %d file(s) without a top-level rules: key or with join mode\n' "$ME" "$url" "$removed" >&2
  if [ -z "$(rule_files "$dest" -print | head -n 1)" ]; then note_skip "$url" "no rule files after pruning"; continue; fi
  CLONED+=("$url")
done

outputs_complete() {
  [ -s "$1" ] && [ -s "$2" ] || return 1
  jq -e '.results | type == "array"' "$1" >/dev/null 2>&1 && jq -e '.runs | type == "array"' "$2" >/dev/null 2>&1
}

collect() {
  local i=$1 status=$2
  local json=$RAW_DIR/${U_STEM[$i]}.json sarif=$RAW_DIR/${U_STEM[$i]}.sarif errfile=$SCRATCH/${U_STEM[$i]}.err
  if outputs_complete "$json" "$sarif"; then
    case "$status" in
      0|1|2)
        jq -c --arg lang "${U_LANG[$i]}" --arg ruleset "${U_RULESET[$i]}" --arg json "$json" --arg sarif "$sarif" \
          --argjson exitCode "$status" \
          '{lang: $lang, ruleset: $ruleset, json: $json, sarif: $sarif, findings: (.results | length),
            filesScanned: (if (.paths.scanned | type) == "array" then (.paths.scanned | length) else -1 end),
            partial: ($exitCode == 2), exitCode: $exitCode}' "$json" >> "$OK_LOG"
        return ;;
    esac
    reason=$(tail -c 800 "$errfile")
  else
    reason="exit $status, output missing or incomplete. $(tail -c 800 "$errfile")"
  fi
  jq -cn --arg lang "${U_LANG[$i]}" --arg ruleset "${U_RULESET[$i]}" --arg json "$json" --arg sarif "$sarif" \
    --arg error "$reason" '$ARGS.named' >> "$FAIL_LOG"
}

BATCH_PID=() BATCH_UNIT=()
drain() {
  local k
  for k in "${!BATCH_PID[@]}"; do
    wait "${BATCH_PID[$k]}"
    collect "${BATCH_UNIT[$k]}" $?
  done
  BATCH_PID=() BATCH_UNIT=()
}
for i in "${!U_RULESET[@]}"; do
  if [ "${U_KIND[$i]}" = clone ] && ! member "${U_RULESET[$i]}" "${CLONED[@]}"; then continue; fi
  semgrep_argv "$i"
  (cd "$TARGET_REAL" && exec "${ARGV[@]}") >/dev/null 2>"$SCRATCH/${U_STEM[$i]}.err" &
  BATCH_PID+=("$!"); BATCH_UNIT+=("$i")
  if [ ${#BATCH_PID[@]} -ge "$JOBS" ]; then drain; fi
done
drain

BIG_LIST=$SCRATCH/oversized.txt
: > "$BIG_LIST"
if [ "$MAX_BYTES" -gt 0 ]; then
  name_args=()
  for lang in "${LANGS[@]}"; do
    while IFS= read -r glob; do
      [ ${#name_args[@]} -eq 0 ] || name_args+=(-o)
      name_args+=(-name "$glob")
    done < <(globs_of "$lang")
  done
  if [ ${#name_args[@]} -gt 0 ]; then
    find "$TARGET_REAL" \( -path "$TARGET_REAL/.git" -o -path "$OUT_REAL" \) -prune -o \
      -type f \( "${name_args[@]}" \) -size +"${MAX_BYTES}"c -print 2>/dev/null \
      | sed "s|^$TARGET_REAL/||" | sort -u > "$BIG_LIST"
  fi
fi

lines_to_json() { jq -Rn '[inputs | select(length > 0)]'; }
jq -n \
  --arg outputDir "$OUTPUT_DIR" --arg rawDir "$RAW_DIR" --arg reposPath "$REPOS_DIR" --arg mode "$MODE" \
  --argjson pro "$([ "$PRO" = 1 ] && echo true || echo false)" \
  --arg excludePattern "$EXCLUDE_PATTERN" --argjson maxTargetBytes "$MAX_BYTES" \
  --slurpfile ok "$OK_LOG" --slurpfile bad "$FAIL_LOG" --slurpfile skip "$SKIP_LOG" \
  --argjson alsoShared "$(printf '%s\n' "${ALSO_SHARED[@]}" | lines_to_json)" \
  --argjson unscoped "$(printf '%s\n' "${UNSCOPED[@]}" | lines_to_json)" \
  --argjson oversized "$(lines_to_json < "$BIG_LIST")" \
  '$ARGS.named | del(.ok, .bad, .skip)
   + {scans: $ok, failed: $bad, skipped: $skip,
      coveredNothing: [$ok[] | select(.filesScanned == 0) | "\(.lang)/\(.ruleset)"]}' \
  > "$SCANS_JSON" || fail "cannot write $SCANS_JSON"

if [ "$(jq '.scans | length' "$SCANS_JSON")" = 0 ]; then
  fail "no scan succeeded; see failed and skipped in $SCANS_JSON"
fi
printf '%s\n' "$SCANS_JSON"
