#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export GIT_CONFIG_COUNT=0
if ! python3 -c 'import pytest, yaml' 2>/dev/null; then
  echo "not run: pytest and PyYAML are needed (nothing is installed for you)" >&2
  exit 1
fi
exec python3 -m pytest "$here" -q -p no:cacheprovider "$@"
