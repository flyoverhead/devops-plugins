#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Teodor Vasquez" GIT_AUTHOR_EMAIL="teodor@example.net"
export GIT_COMMITTER_NAME="Teodor Vasquez" GIT_COMMITTER_EMAIL="teodor@example.net"
export GIT_AUTHOR_DATE="2026-05-14T09:30:00Z" GIT_COMMITTER_DATE="2026-05-14T09:30:00Z"

git init -q -b main
git config core.hooksPath /dev/null
mkdir -p snapcache
printf 'module example.net/kiosk/snapcache\n\ngo 1.22\n' > go.mod
cat > snapcache/disk.go <<'GO'
package snapcache

import (
	"os"
	"path/filepath"
)

// Put stores one rendered snapshot under dir, named after its key.
func Put(dir, key string, png []byte) {
	os.WriteFile(filepath.Join(dir, key+".png"), png, 0666)
}

// Get reads a snapshot back; a missing file yields nil.
func Get(dir, key string) []byte {
	b, err := os.ReadFile(filepath.Join(dir, key+".png"))
	if err != nil {
		return nil
	}
	return b
}
GO
git add -A
git commit -q -m "snapcache: keep rendered kiosk snapshots on disk"
