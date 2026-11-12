#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
export GIT_CONFIG_COUNT=0
if python3 -c 'import pytest, yaml' 2>/dev/null; then
  exec python3 -m pytest "$here" -q -p no:cacheprovider "$@"
fi
exec uv run --no-project --no-python-downloads --with pytest --with pyyaml python -m pytest "$here" -q -p no:cacheprovider "$@"
