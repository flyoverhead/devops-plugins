# Stack recipes and the harness contract

## Contents

- Recipes by stack
- Harness contract
- Example harness (Python, any CLI)
- Loading a module instead of a binary
- Compile claims
- Sandbox notes

## Recipes by stack

| Stack | failure_type | Build argv (in the worktree) | Artifact | Harness loads |
|---|---|---|---|---|
| Go CLI or service | runtime | `go build -o bin/<name> ./cmd/<name>` | `bin/<name>` | hashes and executes the binary |
| Go, claimed compile error | compile | `go build ./...` or `go vet ./...` | none | nothing |
| Python | runtime | the project's build, else `python3 -m py_compile <module file>` | the module file | imports it from `{tree}`, reports `__file__` |
| Bash | runtime | `bash -n <script>` | the script | runs `bash {tree}/<script>` in `{scratch}` |
| TypeScript | runtime | `npm ci` then the repo's build script, as one argv (`["sh", "-c", "npm ci && npm run build"]`) | the built `.js` | runs it with `node` |
| Terraform | compile | `terraform init -backend=false` then `terraform validate` | none | nothing |
| Ansible | compile | `ansible-playbook --syntax-check <playbook>`, or `ansible-lint` on the role | none | nothing |

`npm ci` and `terraform init` download packages or providers. Name that in the plan; if the user
does not approve it, or it fails offline, the outcome is `blocked`.

Behaviour of a role, module or service that needs hosts, a backend or a cluster cannot be shown
here: `blocked`.

## Harness contract

Arguments: `{tree}` (the worktree, a neutral random name), `{scratch}` (a fresh empty directory
for this run only) and the case input as one JSON string. The arms helper fills both placeholders.
Both live in a private temp directory outside the run directory.

Point the application's root (home, data or upload directory) at a nested directory inside
`{scratch}`, e.g. `{scratch}/x/y/home`, never at `{scratch}` itself. A traversal input then lands
in a parent that is still inside `{scratch}`, where the harness can see it, and never reaches the
run directory or the receipts.

1. Locate the artifact under `{tree}`, resolve it, hash its bytes, print
   `PATCH_LOADED {"path": ..., "sha256": ...}`. Hash the same path you then execute or import; a
   hash of some other file binds nothing. `markers.py loaded --artifact <rel> --root {tree}` prints
   the line for you.
2. Set up only inside `{scratch}`. Run the real artifact on the input. Never copy the vulnerable
   function into the harness.
3. Decide `actual` from what happened (files written, output, exit status of the artifact), as a
   small JSON value. Print `PATCH_CASE {"input": <input>, "actual": <actual>}`.
4. Print `PATCH_REACHED` as the last stdout line, then exit: non-zero when the invariant is broken,
   0 when it holds.

The harness is side-blind. It never looks at commit ids, branch names or paths to choose what to
expect, and its expectation is the same on every tree. A crash or a setup error before
`PATCH_REACHED` is a missing observation, never a reproduction.

Planned `expected` values in `repair_scope` use the same vocabulary as `actual`, so a later
comparison is a plain JSON equality.

## Example harness (Python, any CLI)

Invariant in this example: `ledger debit` must never leave a balance below zero.

```python
import hashlib, json, os, subprocess, sys

tree, scratch, raw = sys.argv[1:4]
amount = json.loads(raw)
binary = os.path.realpath(os.path.join(tree, "bin", "ledger"))
with open(binary, "rb") as fh:
    digest = hashlib.sha256(fh.read()).hexdigest()
print("PATCH_LOADED " + json.dumps({"path": binary, "sha256": digest}), flush=True)

book = os.path.join(scratch, "book.json")
subprocess.run([binary, "--book", book, "credit", "10"], check=True, capture_output=True)
done = subprocess.run([binary, "--book", book, "debit", str(amount)], capture_output=True)
balance = json.load(open(book))["balance"]
actual = "negative" if balance < 0 else ("refused" if done.returncode else "debited")
print("PATCH_CASE " + json.dumps({"input": amount, "actual": actual}), flush=True)
print("PATCH_REACHED", flush=True)
sys.exit(1 if balance < 0 else 0)
```

`cases.json` for it:

```json
[
  {"check_id": "overdraw-by-one", "argv": ["python3", "/abs/run/reproduce/poc/harness.py", "{tree}", "{scratch}", "11"]},
  {"check_id": "overdraw-large", "argv": ["python3", "/abs/run/reproduce/poc/harness.py", "{tree}", "{scratch}", "1000000"]},
  {"check_id": "exact-balance", "argv": ["python3", "/abs/run/reproduce/poc/harness.py", "{tree}", "{scratch}", "10"]}
]
```

with `expected` `"refused"` for the two representatives and `"debited"` for the control.

## Loading a module instead of a binary

Python: insert `{tree}` (or its `src/`) at the front of `sys.path`, import the module, then hash
`module.__file__` and print it in `PATCH_LOADED`; that is the file the interpreter actually loaded.
Node: `require.resolve` the built file, hash it, then `require` that path.

## Compile claims

`cases.json` is `[]`; the evidence is the build's own stderr in
`receipts/cases/_build/baseline.stderr` and its `.exit.json`. `expected_diagnostic` is the exact
diagnostic line (path, position and message), copied from that file.

## Sandbox notes

- git inside a sandbox on macOS: if a git call dies with `xcrun_db … Operation not permitted`
  (the developer-tools shim), write `<TMPDIR>/bin/git` as a two-line wrapper that execs a real git
  (e.g. `/opt/homebrew/bin/git`) and prefix `PATH=<TMPDIR>/bin:$PATH` on every later command,
  the helper scripts included. No working git means `blocked`.
- Go: prefix `GOCACHE=<TMPDIR>/gocache GOFLAGS=-buildvcs=false`. The default cache may not be
  writable, and VCS stamping can fail with exit status 72 through the macOS developer-tools git
  shim. The helper records both values in `launch.json`.
- A missing toolchain is a blocker with the exact `cannot start` or `command not found` text from
  the receipt.
