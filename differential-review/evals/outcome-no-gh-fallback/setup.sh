#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Tomas Brandt" GIT_AUTHOR_EMAIL="tomas@example.org"
export GIT_COMMITTER_NAME="Tomas Brandt" GIT_COMMITTER_EMAIL="tomas@example.org"
git init -q -b main
git config core.hooksPath /dev/null
git remote add origin https://git.example.org/me/demo.git
mkdir -p bin
cat > bin/rotate-logs.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
dir="${1:?log directory}"
find "$dir" -name '*.log' -mtime +7 -delete
SH
printf '# demo\n\nHousekeeping scripts.\n' > README.md
git add -A && git commit -q -m "add log rotation script"
cat > bin/rotate-logs.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
dir="${1:?log directory}"
days="${2:-7}"
find "$dir" -name '*.log' -mtime "+$days" -delete
SH
git add -A && git commit -q -m "rotate-logs: make the retention period an argument"
