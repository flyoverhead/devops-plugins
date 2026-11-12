# Python

Every entry: **Bites**, **Spot**, **Fix**.

## Contents

- Code execution and parsing: dynamic execution, subprocess, format strings, unpacking
- Shared state: mutable defaults, class attributes, late binding, loop leakage
- Semantics: identity vs equality, exceptions, numbers, None chains, import shadowing
- Grep set

## Code execution and parsing

### Running data as code

- **Bites:** `eval`, `exec`, `compile`, `__import__` / `importlib.import_module` on input run
  attacker code; so do `pickle.loads`, `yaml.load` without a safe loader and Python 2 `input()`.
- **Spot:** any of these where the argument can come from a request, file or message.
- **Fix:** `ast.literal_eval` or `json` for data, a fixed name-to-module map for plugins,
  `yaml.safe_load`.

### Shell commands from strings

- **Bites:** `subprocess.run(f"tar xf {name}", shell=True)` runs `; rm -rf ~` in a file name.
- **Spot:** every `subprocess`/`os.system`/`os.popen` call, and `shell=True` in particular.
- **Fix:** the list form (`["tar", "xf", name]`) without a shell; `--` before user arguments.

### Format templates from users

- **Bites:** `user_template.format(obj=request)` lets `{obj.__class__.__init__.__globals__}`
  walk to secrets; evaluating an f-string built from input is code execution.
- **Spot:** `.format`/`format_map` where the template string is caller-supplied.
- **Fix:** `string.Template` with a flat dict, or a sandboxed engine with autoescape.

### Unpacking request-sized data

- **Bites:** `a, b = payload` raises on a wrong length after iterating the whole input; a
  huge iterable costs memory and time first.
- **Spot:** tuple unpacking of request bodies, query lists or split results.
- **Fix:** check the length (or `split(sep, 1)`) before unpacking.

## Shared state

### Mutable default arguments

- **Bites:** `def grant(user, roles=[])` builds the list once; one call's appends show up in the
  next caller's roles.
- **Spot:** `=[]`, `={}`, `=set()` in a `def` line.
- **Fix:** default to `None` and create the object in the body.

### Mutable class attributes

- **Bites:** `class Account: permissions = []` shares one list across all instances, so one
  grant reaches every account.
- **Spot:** lists, dicts or sets assigned in a class body and mutated through `self`.
- **Fix:** create them in `__init__`, or use a dataclass `field(default_factory=list)`.

### Closures bound late

- **Bites:** `[lambda: check(r) for r in rules]` — every lambda checks the last rule.
- **Spot:** lambdas or nested functions created in loops or comprehensions.
- **Fix:** bind at creation (`lambda r=r: check(r)`) or `functools.partial`.

### Loop names that outlive the loop

- **Bites:** after `for user in users:` the name `user` still holds the last item and a later
  line authorises it; in contrast the `except ... as e` name is deleted when the handler ends.
- **Spot:** uses of a loop variable after the loop body.
- **Fix:** keep loop variables inside the loop; name the result you mean explicitly.

## Semantics

### `is` where `==` was meant

- **Bites:** `if level is 3` or `if role is "admin"` works for small cached ints and interned
  strings and fails for others.
- **Spot:** `is` against number or string literals.
- **Fix:** `==`; reserve `is` for `None`, `True`, `False` and sentinels.

### Exceptions that turn failure into success

- **Bites:** `try: verify(sig) except Exception: pass` makes every bad signature valid; an
  exception raised inside a handler (a logging call) hides the original one.
- **Spot:** bare `except:` or broad handlers around verification, auth or permission code.
- **Fix:** catch the narrow exception, and fail closed in the handler.

### Floats and integer division

- **Bites:** `0.1 + 0.2 != 0.3`; large integers lose precision as floats; Python 2 `/` floors.
- **Spot:** money, quotas and thresholds compared as floats.
- **Fix:** `decimal.Decimal` or integer minor units.

### Attribute chains on None

- **Bites:** `resp.json().get("user").role` raises mid-chain when a field is missing, often in
  an error path that then skips a check.
- **Spot:** chained attribute access on API results.
- **Fix:** explicit `None` checks, or `getattr(x, "role", None)` with a deliberate default.

### Local files that shadow the standard library

- **Bites:** a `random.py`, `secrets.py`, `email.py`, `types.py` or `test.py` next to the code
  is imported instead of the real module.
- **Spot:** file names in the package that match standard-library modules.
- **Fix:** rename them.

## Grep set

```bash
grep -rn --include='*.py' -E 'def .*=(\[\]|\{\})' .
grep -rn --include='*.py' -E '(eval|exec)\(|pickle\.loads|yaml\.load\(' .
grep -rn --include='*.py' -E 'shell=True' .
grep -rn --include='*.py' -E 'except:' .
grep -rn --include='*.py' -E ' is [0-9"]' .
```
