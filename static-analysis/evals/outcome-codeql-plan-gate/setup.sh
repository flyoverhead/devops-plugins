#!/usr/bin/env bash
set -euo pipefail
git init -q
printf 'module example.com/pinger

go 1.22
' > go.mod
cat > main.go <<'GO'
package main

import (
	"net/http"
	"os/exec"
)

func pingHandler(rw http.ResponseWriter, req *http.Request) {
	host := req.URL.Query().Get("host")
	out, _ := exec.Command("sh", "-c", "ping -c 1 "+host).CombinedOutput()
	_, _ = rw.Write(out)
}

func main() {
	http.HandleFunc("/ping", pingHandler)
	_ = http.ListenAndServe(":8080", nil)
}
GO
cat > LICENSE <<'TXT'
MIT License

Copyright (c) 2026 Example Author

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
TXT
git remote add origin https://github.com/example/pinger.git
git add -A && git commit -q -m init
