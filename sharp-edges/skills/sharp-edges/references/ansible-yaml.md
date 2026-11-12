# Ansible roles and YAML

A role's interface is `defaults/main.yml`, `meta/argument_specs.yml` and any variable its tasks
and templates read. Every entry: **Bites**, **Spot**, **Fix**.

### YAML 1.1 type coercion

- **Bites:** unquoted `yes`, `no`, `on`, `off` become booleans; the country code `NO` becomes
  `false`; `mode: 644` is the decimal 644, not octal; `version: 1.10` becomes `1.1`; the string
  `"false"` is truthy in a Jinja `if`.
- **Spot:** unquoted file modes, version numbers and boolean-looking strings; `when:` on a
  variable that may arrive as a string.
- **Fix:** quote modes (`"0640"`) and versions; real `true`/`false`; `| bool` in conditions;
  `type: bool` in the argument spec.

### Security switch one variable away

- **Bites:** `validate_certs: "{{ app_validate_certs | default(false) }}"` or
  `mode: "{{ app_secret_mode | default('0644') }}"` ships the unsafe value to everyone who sets
  nothing.
- **Spot:** `default(false)`, `default('0644')` and similar on TLS, mode or auth parameters.
- **Fix:** the safe value as the default; the unsafe one only by explicit opt-in.

### `no_log` that leaks anyway

- **Bites:** `no_log` is per task. A `loop` label, a registered result printed by `debug`, or
  a later task that templates the secret prints it again; `no_log: "{{ app_debug }}"` defaulting
  to `false` protects nothing.
- **Spot:** secrets in loops, registers and `debug`; `no_log` driven by a variable.
- **Fix:** `no_log: true` on every task that touches the secret, `loop_control.label`, no debug
  of registers that hold it.

### Privilege granted too widely

- **Bites:** with privilege escalation switched on for the whole play, a template fed by
  inventory or an API response is rendered by root, as is everything else.
- **Spot:** play-level `become`; roles that never scope it.
- **Fix:** `become` on the tasks that need it.

### Shell commands built from variables

- **Bites:** `shell: "useradd {{ app_user }}"` executes whatever the inventory, a fact or an API
  response put in `app_user`; a password variable with a space or `;` breaks out of the command.
- **Spot:** `shell` and `command` with `{{ }}` in the string.
- **Fix:** a dedicated module; otherwise `command` with `argv:`, or `| quote` on each value.

### Variable precedence works against hardening

- **Bites:** `defaults/` loses to everything, so an unsafe default is exactly what runs when
  nobody overrides it; a safe value placed in `vars/` beats inventory and cannot be tightened
  per environment either.
- **Spot:** security settings in `vars/main.yml`; unsafe values in `defaults/main.yml`.
- **Fix:** safe values in `defaults/`, with argument-spec validation for overrides.

### Jinja defaults that fall through

- **Bites:** `default('*')` on allowed hosts, `default('')` on a password, `default(false)` on
  auth: an undefined variable silently becomes the widest setting.
- **Spot:** `default(` on auth, network and secret variables in tasks and templates.
- **Fix:** no default; `ansible.builtin.assert` (or a required argument) before first use.

### Argument specs without teeth

- **Bites:** `meta/argument_specs.yml` declares `type: str` for a mode or `type: bool` with a
  `false` default, and nothing is `required` or limited by `choices`.
- **Spot:** security variables with no `required: true`, `choices:` or `no_log: true`.
- **Fix:** `choices` for modes and algorithms, `required` for secrets, `no_log` on secret options.

### Failures ignored on security tasks

- **Bites:** `ignore_errors: true` or `failed_when: false` on a certificate check, firewall rule
  or hardening step reports success when the control is missing.
- **Spot:** those keys on any task with a security purpose.
- **Fix:** let it fail; handle a known benign error with a narrow `failed_when` expression.
