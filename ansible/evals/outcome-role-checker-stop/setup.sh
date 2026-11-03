#!/usr/bin/env bash
set -euo pipefail
bash "$(dirname "$0")/../outcome-role-checker-restructure/setup.sh"
echo '- Local note, not committed yet.' >> roles/node_exporter/README.md
