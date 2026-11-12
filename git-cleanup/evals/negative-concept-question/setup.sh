#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Kenji Mori" GIT_AUTHOR_EMAIL="kenji@example.org"
export GIT_COMMITTER_NAME="Kenji Mori" GIT_COMMITTER_EMAIL="kenji@example.org"
git init -q -b main
git config core.hooksPath /dev/null
printf 'retries: 3\n' > settings.yml
git add -A && git commit -q -m "Initial settings"
git switch -q -c tweak/retries
printf 'retries: 5\n' > settings.yml
git commit -q -am "Raise retries to 5"
printf 'retries: 5\ntimeout: 30\n' > settings.yml
git commit -q -am "Add a timeout"
git switch -q main
git merge -q --squash tweak/retries >/dev/null
git commit -q -m "Tune retries and timeout (#9)"
