#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Lena Sorvik" GIT_AUTHOR_EMAIL="lena@example.com"
export GIT_COMMITTER_NAME="Lena Sorvik" GIT_COMMITTER_EMAIL="lena@example.com"
git init -q -b main
git config core.hooksPath /dev/null
mkdir -p cmd/demo-service internal/imaging tools

printf 'module example.com/demo/demo-service\n\ngo 1.23\n' > go.mod

cat > cmd/demo-service/main.go <<'GO'
package main

import (
	"log"
	"net/http"

	"example.com/demo/demo-service/internal/imaging"
)

func main() {
	http.HandleFunc("/v1/thumb", imaging.Thumbnail)
	http.HandleFunc("/v1/stamp", imaging.Stamp)
	http.HandleFunc("/v1/squeeze", imaging.Squeeze)
	http.HandleFunc("/v1/probe", imaging.Probe)
	http.HandleFunc("/v1/version", imaging.Version)
	log.Println("imaging up on :7311")
	log.Fatal(http.ListenAndServe(":7311", nil))
}
GO

cat > internal/imaging/thumb.go <<'GO'
package imaging

import (
	"log"
	"net/http"
	"os/exec"
)

// Thumbnail scales an uploaded picture down to 160px.
func Thumbnail(w http.ResponseWriter, req *http.Request) {
	pic := req.URL.Query().Get("pic")
	if pic == "" {
		http.Error(w, "pic is required", http.StatusBadRequest)
		return
	}
	cmd := exec.Command("/bin/sh", "-c", "magick /srv/uploads/"+pic+" -thumbnail 160x160 /srv/cache/t.webp")
	if msg, err := cmd.CombinedOutput(); err != nil {
		log.Printf("thumbnail: %v: %s", err, msg)
		http.Error(w, "could not scale picture", http.StatusUnprocessableEntity)
		return
	}
	http.ServeFile(w, req, "/srv/cache/t.webp")
}
GO

cat > internal/imaging/stamp.go <<'GO'
package imaging

import (
	"context"
	"fmt"
	"net/http"
	"os/exec"
	"time"
)

// Stamp writes a caption across the bottom of a picture.
func Stamp(w http.ResponseWriter, req *http.Request) {
	caption := req.PostFormValue("caption")
	ctx, cancel := context.WithTimeout(req.Context(), 20*time.Second)
	defer cancel()
	line := fmt.Sprintf(`magick /srv/uploads/base.png -gravity south -annotate +0+8 "%s" /srv/cache/s.png`, caption)
	if err := exec.CommandContext(ctx, "bash", "-c", line).Run(); err != nil {
		http.Error(w, "caption rejected by renderer", http.StatusBadGateway)
		return
	}
	fmt.Fprintln(w, "stamped")
}
GO

cat > internal/imaging/squeeze.go <<'GO'
package imaging

import (
	"net/http"
	"os/exec"
)

// Squeeze recompresses one cached file with the packaged helper.
func Squeeze(w http.ResponseWriter, req *http.Request) {
	level := req.Header.Get("X-Squeeze-Level")
	helper := exec.Command("/opt/demo/bin/squeeze.sh", "/srv/cache/t.webp", level)
	if err := helper.Run(); err != nil {
		http.Error(w, "squeeze helper exited non-zero", http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusOK)
}
GO

cat > internal/imaging/probe.go <<'GO'
package imaging

import (
	"net/http"
	"os/exec"
	"path/filepath"
)

// Probe reports the format and size of one upload.
func Probe(w http.ResponseWriter, req *http.Request) {
	name := filepath.Base(req.URL.Query().Get("pic"))
	info, err := exec.Command("magick", "identify", "-format", "%m %wx%h", filepath.Join("/srv/uploads", name)).Output()
	if err != nil {
		http.Error(w, "unreadable picture", http.StatusNotFound)
		return
	}
	_, _ = w.Write(info)
}
GO

cat > internal/imaging/version.go <<'GO'
package imaging

import (
	"net/http"
	"os/exec"
)

// Version prints the first line of the renderer's version banner.
func Version(w http.ResponseWriter, req *http.Request) {
	banner, err := exec.Command("sh", "-c", "magick -version | sed -n 1p").Output()
	if err != nil {
		http.Error(w, "renderer missing", http.StatusServiceUnavailable)
		return
	}
	_, _ = w.Write(banner)
}
GO

cat > tools/squeeze.sh <<'BASH'
#!/usr/bin/env bash
# Shipped as /opt/demo/bin/squeeze.sh in the container image.
set -eu
target="$1"
level="${2:-2}"
sh -c "cwebp -q 8${level} ${target} -o ${target}.tmp && mv ${target}.tmp ${target}"
BASH
chmod +x tools/squeeze.sh

cat > README.md <<'MD'
# demo-service

Picture thumbnailer behind the upload form. `tools/squeeze.sh` is copied into the image as
`/opt/demo/bin/squeeze.sh`.
MD

git add -A && git commit -q -m "imaging: thumbnail, caption and recompress endpoints"
