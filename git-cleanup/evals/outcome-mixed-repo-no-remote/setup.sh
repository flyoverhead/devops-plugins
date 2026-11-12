#!/usr/bin/env bash
set -euo pipefail
export GIT_AUTHOR_NAME="Ines Okafor" GIT_AUTHOR_EMAIL="ines@example.org"
export GIT_COMMITTER_NAME="Ines Okafor" GIT_COMMITTER_EMAIL="ines@example.org"
tick=0
at() {
  tick=$((tick + 1))
  GIT_AUTHOR_DATE=$(printf '2026-03-%02dT%02d:00:00Z' "$1" "$tick")
  export GIT_AUTHOR_DATE GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
}

git init -q -b main
git config core.hooksPath /dev/null
mkdir -p tideline
cat > tideline/cli.py <<'PY'
import sys
from datetime import date


def show(day: date, height_m: float) -> str:
    return f"{day.isoformat()}  {height_m:.2f} m"


if __name__ == "__main__":
    print(show(date.today(), float(sys.argv[1])))
PY
printf '# tideline\n\nPrints tide tables for a harbour.\n' > README.md
at 1; git add -A && git commit -q -m "Start tideline: print one tide reading"

git switch -q -c develop
git switch -q main

git switch -q -c fix/locale-dates
cat > tideline/cli.py <<'PY'
import locale
import sys
from datetime import date


def show(day: date, height_m: float) -> str:
    locale.setlocale(locale.LC_TIME, "")
    return f"{day.strftime('%x')}  {height_m:.2f} m"


if __name__ == "__main__":
    print(show(date.today(), float(sys.argv[1])))
PY
at 2; git commit -q -am "Format reading dates with the user's locale"
git switch -q main
at 2; git merge -q --no-ff fix/locale-dates -m "Merge branch 'fix/locale-dates'"

git switch -q -c spike/rust-port
mkdir -p port
printf '[package]\nname = "tideline"\nversion = "0.0.1"\nedition = "2021"\n' > port/Cargo.toml
at 3; git add -A && git commit -q -m "Try a Rust port: cargo manifest"
printf 'fn main() {\n    println!("tideline");\n}\n' > port/main.rs
at 3; git add -A && git commit -q -m "Rust port: stub main"
git switch -q main

git switch -q -c feat/csv-export
cat > tideline/export.py <<'PY'
import csv
import io


def to_csv(rows):
    buf = io.StringIO()
    out = csv.writer(buf)
    for day, height in rows:
        out.writerow([day, f"{height:.2f}"])
    return buf.getvalue()
PY
at 4; git add -A && git commit -q -m "Add to_csv for tide rows"
cat > tideline/test_export.py <<'PY'
from tideline.export import to_csv


def test_two_rows():
    assert to_csv([("2026-03-04", 1.5), ("2026-03-05", 2.25)]) == "2026-03-04,1.50\r\n2026-03-05,2.25\r\n"
PY
at 4; git add -A && git commit -q -m "Test CSV export"

git switch -q -c feat/csv-export-headers
cat > tideline/export.py <<'PY'
import csv
import io


def to_csv(rows, header=("date", "height_m")):
    buf = io.StringIO()
    out = csv.writer(buf)
    if header:
        out.writerow(header)
    for day, height in rows:
        out.writerow([day, f"{height:.2f}"])
    return buf.getvalue()
PY
at 5; git commit -q -am "Let CSV export write a header row"

git switch -q main
git merge -q --squash feat/csv-export >/dev/null
at 6; git commit -q -m "Add CSV export for tide tables (#57)"
printf '# tideline\n\nPrints tide tables for a harbour. Version 0.4.0.\n' > README.md
at 7; git commit -q -am "Bump version to 0.4.0"
