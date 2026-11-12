package demo

import (
	"database/sql"
	"fmt"
	"html/template"
	"net/http"
	"os"
	"os/exec"
	"strconv"
)

func shellConcat(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")
	// ruleid: variant-taint-go
	_ = exec.Command("sh", "-c", "gzip -d /srv/in/"+name).Run()
}

func shellSprintf(w http.ResponseWriter, r *http.Request) {
	line := fmt.Sprintf("wc -l %s", r.FormValue("file"))
	// ruleid: variant-taint-go
	_ = exec.Command("bash", "-c", line).Run()
}

func argvForm(w http.ResponseWriter, r *http.Request) {
	// ok: variant-taint-go
	_ = exec.Command("gzip", "-d", r.FormValue("file")).Run()
}

func constantShell() {
	// ok: variant-taint-go
	_ = exec.Command("sh", "-c", "uptime").Run()
}

func numeric(w http.ResponseWriter, r *http.Request) {
	n, _ := strconv.Atoi(r.FormValue("n"))
	// ok: variant-taint-go
	_ = exec.Command("sh", "-c", fmt.Sprint("seq ", n)).Run()
}

func sqlConcat(db *sql.DB, r *http.Request) {
	// ruleid: variant-taint-go
	_, _ = db.Query("SELECT * FROM jobs WHERE owner = '" + r.FormValue("owner") + "'")
}

func sqlBound(db *sql.DB, r *http.Request) {
	// ok: variant-taint-go
	_, _ = db.Query("SELECT * FROM jobs WHERE owner = $1", r.FormValue("owner"))
}

func readFromEnv() {
	// ruleid: variant-taint-go
	_, _ = os.ReadFile(os.Getenv("DEMO_CONFIG"))
}

func unsafeHTML(r *http.Request) template.HTML {
	// ruleid: variant-taint-go
	return template.HTML(r.FormValue("bio"))
}
