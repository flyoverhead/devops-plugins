#!/usr/bin/env bash
set -u

file=$(jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0

case "$file" in
  *.go) ;;
  *) exit 0 ;;
esac
case "$file" in
  */vendor/* | *.pb.go) exit 0 ;;
esac

command -v go >/dev/null 2>&1 || exit 0
[ -f "$file" ] || exit 0

dir=$(dirname "$file")
probe=$dir
while [ ! -f "$probe/go.mod" ]; do
  case "$probe" in / | .) exit 0 ;; esac
  probe=$(dirname "$probe")
done

cd "$dir" || exit 0
if ! out=$(go vet . 2>&1); then
  printf '%s\n' "$out" >&2
  exit 2
fi
exit 0
