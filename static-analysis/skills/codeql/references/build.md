# Building the database

## Contents

- Logging every rung
- The ladder for compiled languages
- macOS arm64: exit 137
- Fixes before retrying a rung
- Improving a poor database

## Logging every rung

Source the logger in the same Bash call as the build; nothing survives between calls.

```bash
OUTPUT_DIR=/abs/tmp/codeql-repo_1; DB="$OUTPUT_DIR/codeql.db"
source "${CLAUDE_SKILL_DIR}/scripts/build_log.sh" || exit 1
log_step "rung 1: autobuild"
run_logged codeql database create "$DB" --overwrite --source-root=. --language=go
```

`build_log.sh` sets `LOG_FILE` (default `$OUTPUT_DIR/build.log`), turns on `pipefail`, and
does not set `-e`. `run_logged` writes the command, its output and `-> exit N` to the log and
returns the command's own status through the `tee`. `log_step`, `log_cmd` and `log_result`
write single lines.

## The ladder for compiled languages

Stop at the first rung that succeeds and passes the quality gate. Log every rung, including
the ones that fail.

1. **Autobuild.** `codeql database create "$DB" --language=<lang> --source-root=. --overwrite`
   with no `--command`.
2. **Custom command** from the detected build system, always in double quotes:
   `--command="$BUILD_CMD"`.

   | Build system | Command |
   |---|---|
   | Go | `go build ./...` |
   | Make | `make -j"$(getconf _NPROCESSORS_ONLN)"` |
   | CMake | `cmake -S . -B build && cmake --build build` (as a script, see rung 3) |
   | Maven | `mvn -B -DskipTests package` |
   | Gradle | `./gradlew --no-daemon -x test assemble` |
   | Cargo | `cargo build --locked` |
   | .NET | `dotnet build --no-incremental` |
   | Other | the project's build script or the README's build section |

3. **Multi-step trace** when the build needs several commands or a configure step:
   `codeql database init "$DB" --language=<lang> --source-root=. --overwrite`, then
   `codeql database trace-command "$DB" -- <step>` for each step, each gating the next, then
   `codeql database finalize "$DB"`. Any failed step fails the rung.
4. **`--build-mode=none`**, last resort, for java, csharp, cpp and rust only. Never go or
   swift. Report it as partial analysis.

On macOS arm64, an exit 137 from rungs 1–2 switches to the sub-ladder below before rung 3.

## macOS arm64: exit 137

Exit 137 here is not a real build failure. Apple's system tools (`/usr/bin/make`, `clang`)
are arm64e, and CodeQL's `libtrace.dylib` is arm64 only, so the tracer is killed on load.
Confirm all three: `uname -sm` prints `Darwin arm64`; `lipo -archs` on CodeQL's
`libtrace.dylib` lacks `arm64e`; `lipo -archs /usr/bin/make` includes `arm64e`.

Sub-ladder, in order:

1. **Homebrew toolchain.** Use Homebrew `clang`/`gcc` and `make` (plain arm64). Build once
   normally, take the compile commands from a dry run (`make -n`), then `database init`,
   `trace-command` per compiler call, `finalize`.
2. **Rosetta.** Run the whole pipeline under `arch -x86_64` with an x86_64 CodeQL.
3. **System compiler once more**, expecting 137 or 134, to confirm the cause for the report.
4. **Ask the user.**

`--build-mode=none` only after all four. Never use it as a shortcut around 137.

## Fixes before retrying a rung

Apply in order; after each, retry the same rung. Anything that deletes in the repo or
installs dependencies must be in the approved plan or asked about first. No global installs.

1. Remove the half-built database (`--overwrite`, or delete `$DB` after checking the path).
2. Clean build caches: `make clean`, `rm -rf build/` for CMake, `mvn clean`,
   `./gradlew clean`, `cargo clean`.
3. Install the project's own dependencies locally (`go mod download`, `npm ci`,
   `pip install -r requirements.txt` inside a venv, `mvn dependency:go-offline`).
4. Private registry authentication: ask the user to set it up; never handle their tokens.

## Improving a poor database

The quality gate failed or `project_files` is far below the source count from detection:

- adjust `--source-root` to the directory the build actually compiles;
- "no source code seen" during extraction → force a clean rebuild (fixes 1–2) so the compiler
  really runs under the tracer;
- extractor options: `CODEQL_EXTRACTOR_CPP_OPTION_TRAP_HEADERS=true` for header-heavy C/C++,
  `CODEQL_EXTRACTOR_JAVA_OPTION_JDK_VERSION=<n>` when the JDK is misdetected;
- then the next rung.

Compiled languages only cover files the build compiled: conditional compilation, disabled
targets and generated code that never compiled are not in the database. Say so in the report.
