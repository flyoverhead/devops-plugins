# Terraform modules

A module's interface is its `variable` blocks plus every place a variable reaches a resource.
Every entry: **Bites**, **Spot**, **Fix**.

### Insecure variable defaults

- **Bites:** `default = ["0.0.0.0/0"]` on an ingress CIDR, `default = ""` on a password: every
  caller who sets nothing deploys the open version.
- **Spot:** defaults on CIDR, password, public-access and encryption variables.
- **Fix:** make the caller supply the value, reject open ranges in `validation`, mark secrets `sensitive`.

```hcl
variable "admin_cidrs" {
  type = list(string)
  validation {
    condition     = length(var.admin_cidrs) > 0 && !contains(var.admin_cidrs, "0.0.0.0/0")
    error_message = "List the admin networks; 0.0.0.0/0 is not accepted."
  }
}
```

### What `sensitive` does not do

- **Bites:** `sensitive = true` hides values in plan output only. State keeps them in plain
  text; `nonsensitive()`, a `local-exec` command line or a provider attribute that is not marked
  sensitive prints them.
- **Spot:** secrets passed to `local-exec`, outputs wrapped in `nonsensitive()`, state stored
  without encryption.
- **Fix:** keep secrets out of Terraform where possible (references to a secret store); an
  encrypted backend with restricted access.

### Controls behind a count that defaults to off

- **Bites:** `count = var.enable_firewall ? 1 : 0` with `default = false` means the firewall is
  simply not created, and nothing in the plan says so.
- **Spot:** `count`/`for_each` gated by a boolean on a security resource.
- **Fix:** default to on; make turning it off an explicit, validated choice.

### Provider switches that drop TLS checks

- **Bites:** `insecure = true`, `skip_tls_verify = true`, `allow_unverified_ssl = true` in a
  provider block or a variable wired to it.
- **Spot:** those arguments and the variables that feed them.
- **Fix:** supply the CA instead; no module variable that can flip them.

### Lifecycle guards lost in a refactor

- **Bites:** removing `prevent_destroy`, or renaming a resource without a `moved` block, turns
  the next plan into a delete of a database or volume.
- **Spot:** diffs or modules where stateful resources lack `prevent_destroy`; renames without
  `moved`.
- **Fix:** `prevent_destroy` on stateful resources; `moved` blocks for every rename.

### Inputs without validation

- **Bites:** a TLS policy string, a port range or a retention period accepts any value, so
  `TLS-1-0` or `0` days pass straight through.
- **Spot:** security-relevant `string` and `number` variables with no `validation` block.
- **Fix:** `validation` with an allowlist or both bounds.
