# shellcheck shell=bash
# Sourced, not executed: `. build_log.sh || exit 1`. No `set -e`, so callers see every exit status.

if [ -z "${LOG_FILE:-}" ]; then
  if [ -z "${OUTPUT_DIR:-}" ]; then
    echo "build_log.sh: set OUTPUT_DIR or LOG_FILE before sourcing" >&2
    return 1
  fi
  LOG_FILE="$OUTPUT_DIR/build.log"
fi
if ! { mkdir -p "$(dirname "$LOG_FILE")" && : >> "$LOG_FILE"; } 2>/dev/null; then
  echo "build_log.sh: cannot write $LOG_FILE" >&2
  return 1
fi
export LOG_FILE
set -o pipefail

log_step() {
  printf '\n== %s  %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

log_cmd() {
  local line="\$"
  local a
  for a in "$@"; do line="$line $(printf '%q' "$a")"; done
  printf '%s\n' "$line" | tee -a "$LOG_FILE"
}

log_result() {
  printf -- '-> exit %s\n' "$1" | tee -a "$LOG_FILE"
}

run_logged() {
  local rc
  log_cmd "$@"
  "$@" 2>&1 | tee -a "$LOG_FILE"
  rc=${PIPESTATUS[0]}
  log_result "$rc"
  return "$rc"
}
