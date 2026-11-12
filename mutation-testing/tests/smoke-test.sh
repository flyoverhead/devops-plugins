#!/usr/bin/env bash
set -euo pipefail

script_dir=${BASH_SOURCE[0]%/*}
[[ "$script_dir" == "${BASH_SOURCE[0]}" ]] && script_dir=.
script_dir="$(cd "$script_dir" && pwd -P)"
plugin="${script_dir%/tests}"
validator="$script_dir/validate_report.py"
fixtures="$script_dir/fixtures"
case_name="outcome-weak-suite-analysis"

usage() {
  cat <<'TXT'
smoke-test.sh: validator self-test plus one real outcome eval.

  DETERMINISTIC_ONLY=yes stop after the validator self-test (any value but 0/no/false)
  RUNS=1                 eval runs
  MODEL=sonnet           agent model
  JUDGE_MODEL=sonnet     LLM-grader model
  MAX_COST_USD=10        cost ceiling for the eval
  KEEP_ARTIFACTS=1       keep the work directory (always kept on failure)
  SMOKE_RUN_ROOT_BASE=/tmp  where the eval keeps its e-* run directories

The eval half needs `claude` on PATH and ANTHROPIC_API_KEY; without them it exits 2.
TXT
}

say() { printf 'smoke: %s\n' "$*"; }
die() { printf 'smoke: FAIL: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
  "") ;;
  *) usage >&2; exit 2 ;;
esac

expect_rejection() {
  local file="$1" reason="$2" out
  out="$(python3 "$validator" --expect-fail "$fixtures/$file")" || die "$file was accepted"
  grep -qF -- "$reason" <<<"$out" || die "$file rejected, but not for: $reason"
  say "rejected $file ($reason)"
}

python3 "$validator" "$fixtures/report-correct.md" >/dev/null || die "report-correct.md was rejected"
say "accepted report-correct.md"
expect_rejection report-both-equivalent.md 'on line 42 is listed as equivalent, but it differs'
expect_rejection report-none-equivalent.md 'on line 42 is not listed as equivalent'

case "${DETERMINISTIC_ONLY:-}" in
  ""|0|no|false) ;;
  *) say "validator self-test passed; eval half skipped"; exit 0 ;;
esac

command -v claude >/dev/null 2>&1 || { say "claude is not on PATH; eval half not run"; exit 2; }
[[ -n "${ANTHROPIC_API_KEY:-}" ]] || { say "ANTHROPIC_API_KEY is unset; eval half not run"; exit 2; }

caller_tmp="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
run_base="$(cd "${SMOKE_RUN_ROOT_BASE:-/tmp}" && pwd -P)"
work="$(mktemp -d "$caller_tmp/mutation-smoke.XXXXXX")"
sandbox="$work/sandbox"
roots_file="$work/out/run-roots.txt"
mkdir -p "$sandbox" "$work/out"
: >"$roots_file"
ok=0

finish() {
  if [[ "$ok" == 1 && "${KEEP_ARTIFACTS:-0}" != 1 ]]; then
    local root
    while IFS= read -r root; do
      [[ "${root##*/}" =~ ^e-[A-Za-z0-9]+$ ]] || continue
      chmod -R u+rwx "$root" 2>/dev/null || true
      rm -rf "$root"
    done <"$roots_file"
    chmod -R u+rwx "$work" 2>/dev/null || true
    rm -rf "$work"
  else
    say "artifacts kept in $work (eval run directories listed in $roots_file)"
  fi
}
trap finish EXIT

json="$work/out/result.json"
say "running $case_name (runs=${RUNS:-1}, model=${MODEL:-sonnet})"
eval_args=(
  plugin eval "$plugin"
  --case "$case_name"
  --runs "${RUNS:-1}"
  --threshold 1
  --ablation none
  --model "${MODEL:-sonnet}"
  --judge-model "${JUDGE_MODEL:-sonnet}"
  --max-cost-usd "${MAX_COST_USD:-10}"
  --allow-tools Write "Bash(printenv TMPDIR)"
  --trust-plugin --scaffold --keep-temp --no-publish
  --output-dir "$work/out"
  --json "$json"
)
eval_rc=0
env TMPDIR="$sandbox" claude "${eval_args[@]}" || eval_rc=$?
[[ -s "$json" ]] || die "eval wrote no result JSON (exit $eval_rc)"

python3 - "$json" "$roots_file" "$caller_tmp" "$run_base" <<'PYCODE' || die "eval result rejected (exit $eval_rc)"
import json, os, re, sys
data = json.load(open(sys.argv[1]))
if data.get("partial"):
    sys.exit("partial run")
if not data.get("cases"):
    sys.exit("no cases ran")
runs = [run for case in data["cases"] for arm in case["arms"].values() for run in arm]
if not runs:
    sys.exit("no runs recorded")
scores = [run["score"] for run in runs]
roots = set()
for run in runs:
    root = os.path.dirname(os.path.dirname(run.get("tracePath") or ""))
    parent = os.path.dirname(os.path.realpath(root))
    if re.fullmatch(r"e-[A-Za-z0-9]+", os.path.basename(root)) and parent in sys.argv[3:5]:
        roots.add(root)
with open(sys.argv[2], "w") as fh:
    fh.writelines(r + "\n" for r in sorted(roots))
if min(scores) < 1:
    sys.exit(f"score below 1: {scores}")
print(f"smoke: eval scores {scores}")
PYCODE

search=("$sandbox")
while IFS= read -r root; do
  chmod u+rwx "$root" 2>/dev/null || true
  [[ -d "$root/sealed" ]] && chmod u+rwx "$root/sealed" 2>/dev/null
  search+=("$root")
done <"$roots_file"

reports=()
while IFS= read -r -d '' found; do
  reports+=("$found")
done < <(find "${search[@]}" -name mutation-testing-report.md -type f -print0 2>/dev/null)
[[ ${#reports[@]} -gt 0 ]] || die "the run left no report in its own directories"
for r in "${reports[@]}"; do
  python3 "$validator" "$r" || die "validator rejected $r"
done

ok=1
say "all checks passed, ${#reports[@]} report(s) validated"
