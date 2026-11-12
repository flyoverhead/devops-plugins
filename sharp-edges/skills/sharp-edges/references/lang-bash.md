# Bash

Every entry: **Bites**, **Spot**, **Fix**. Scripts are interfaces too: their arguments and the
environment variables they read are the choice points.

### Unquoted expansions

- **Bites:** `$file` with a space becomes two arguments; `*` in a value expands to every file;
  `for f in $(ls)` splits names.
- **Spot:** unquoted `$var`, `$(...)`, `$@`.
- **Fix:** quote every expansion; arrays as `"${args[@]}"`; `find -print0` with `read -d ''`.

### Empty variable in a destructive command

- **Bites:** `rm -rf "$BUILD_ROOT/"` with `BUILD_ROOT` unset deletes `/`;
  a mirror step `rsync -a --delete out/ "$MIRROR"` whose `MIRROR` came back blank prunes
  the working directory instead.
- **Spot:** `rm`, `rsync --delete`, `chmod -R`, `chown -R` on variable paths.
- **Fix:** `set -u` and `${BUILD_ROOT:?BUILD_ROOT is required}`.

### Gaps in `set -e`

- **Bites:** errors inside `if`, `while`, `&&` and `||` conditions, and in functions called
  from them, do not stop the script; `local out=$(cmd)` returns the status of `local`.
- **Spot:** critical commands in conditions; `local x=$(` and `export x=$(`.
- **Fix:** declare, then assign; check critical commands explicitly.

### Pipelines that hide failures

- **Bites:** without `pipefail` only the last command's status counts; `curl -s url | sh` runs
  whatever arrived, including half a script.
- **Spot:** pipelines feeding a shell or a deploy step; `curl` or `wget` piped to `sh`/`bash`.
- **Fix:** `set -o pipefail`; download to a file, verify a checksum, then run it.

### Patterns inside tests

- **Bites:** in `[[ $token == $expected ]]` the right side is a glob, so `expected='*'` matches
  everything; `[ $a = $b ]` breaks on empty values.
- **Spot:** unquoted right-hand sides in `[[ ]]`, unquoted operands in `[ ]`.
- **Fix:** quote the right side (`== "$expected"`); prefer `[[ ]]`.

### Secrets in argv and traces

- **Bites:** `set -x` prints the expanded password; `cli --password "$PW"` is readable in `ps`
  by every local user.
- **Spot:** `set -x` in scripts that touch secrets; secrets passed as arguments.
- **Fix:** `--password-stdin` or a 0600 file; `set +x` around secret handling; masked CI
  variables.

### Re-parsing values

- **Bites:** `eval "$cmd"`, `bash -c "deploy $TARGET"` and `ssh host "cd $DIR && make"`
  re-parse values as shell code.
- **Spot:** `eval`, `bash -c`/`sh -c` with expansions, remote commands built from variables.
- **Fix:** arrays for commands; `printf '%q'` for values sent to a remote shell.

### Temporary files

- **Bites:** `/tmp/app.$$` is predictable and can be pre-created as a symlink; files written
  under the default umask are world-readable.
- **Spot:** fixed or PID-based temp names; secrets written without a umask.
- **Fix:** `mktemp`, `umask 077`, `trap 'rm -f "$tmp"' EXIT`.

## Grep set

```bash
grep -rn --include='*.sh' -E 'rm -rf "?\$' .
grep -rn --include='*.sh' -E 'set -x|eval |local [a-z_]+=\$\(' .
grep -rn --include='*.sh' -E '(curl|wget)[^|]*\| *(ba)?sh' .
grep -rn -L --include='*.sh' -E 'set -[a-z]*u|set -o nounset' .
```

The last line lists scripts that never turn on `set -u`.

If `shellcheck` is on the machine, its SC2086, SC2155 and SC2115 codes cover several of these.
Do not install it.
