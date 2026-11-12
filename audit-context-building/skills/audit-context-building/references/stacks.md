# Stacks

How the four orientation questions (parts, ways in, actors, lasting state) and the notion of a
black-box callee translate to each stack, and the traps that make a path look safer than it is.

## Contents

- [All stacks](#all-stacks)
- [Go and Python services](#go-and-python-services)
- [TypeScript](#typescript)
- [CLIs and Bash](#clis-and-bash)
- [Ansible](#ansible)
- [Terraform](#terraform)
- [GitLab CI](#gitlab-ci)

## All stacks

- A callee whose source is in reach (same repo, `vendor/`, installed collection, module
  cache) is read, every path, not only the one the caller expects. If a property holds on
  three paths out of four, it is an assumption, and the fourth path is named.
- Paths that quietly break a property: a zero value returned together with a nil error; a
  check that runs only when a flag or setting is on; an early return placed before the
  validation; a default branch in a switch; an error that is logged and then ignored.
- A callee with no source in reach (remote API, cloud provider, external command, container
  image, remote include) is treated as hostile. Record what is sent to it, what the unit
  assumes comes back, and which results nothing rules out (empty, partial, slow, wrong type).

## Go and Python services

| Question | Where to look |
|---|---|
| Ways in | route registrations, gRPC/RPC methods, queue consumers, scheduled jobs, signal handlers |
| Actors | whatever the auth layer derives identity from; headers set "by the gateway" are an assumption about deployment |
| Lasting state | database rows, caches, sessions, files on disk, package-level maps and globals |
| Black boxes | third-party HTTP APIs, secret stores, SDK calls without vendored source |

- Identity and permission checks often live in middleware or a router group. Record the line
  where the check really happens, and list which routes pass through it and which do not.
- Concurrency is shared state: a read-modify-write without a transaction, a map guarded by
  different mutexes in different places, a goroutine that outlives the request.
- Go: note error paths that return a zero value with a nil error, and context cancellation
  that can stop a sequence of writes halfway.
- Python: exceptions swallowed by a broad `except`, mutable default arguments, and decorators
  that do the checking (read the decorator, not its name).

## TypeScript

- Ways in: route handlers, middleware chains (order of `use` calls matters), message
  listeners, exported functions of a library.
- Values from `JSON.parse`, request bodies and `any` carry no type guarantee at runtime;
  a type annotation establishes nothing. Look for a runtime schema check.
- A promise whose rejection nobody awaits leaves the success path assumed.

## CLIs and Bash

| Question | Where to look |
|---|---|
| Ways in | flags, positional arguments, environment variables, stdin, files read |
| Actors | whoever runs it: a person, cron, a CI job with its own variables |
| Lasting state | files written, lock files, remote systems changed |
| Black boxes | every external command, including `curl`, `jq`, `ssh`, package managers |

- Record quoting as a fact: an unquoted `$var` undergoes word splitting and globbing.
- Record which exit codes the script relies on and what happens on failure under its `set`
  options. `set -e` does nothing inside a function called as an `if`/`&&`/`||` condition, in
  any but the last command of a pipeline without `pipefail`, or for a command substitution
  assigned in the same statement as `local`.

## Ansible

- The unit is a task file, a handler or a template.
- Preconditions sit in `defaults/`, `meta/argument_specs.yml` or an `assert` task; say which.
  A value only in `defaults/` establishes nothing about what the inventory will pass.
- Precedence decides who sets a value: inventory and play vars beat role defaults, role
  `vars/` beat inventory. Record which layer the unit actually gets the value from.
- `when:` on `include_tasks` applies to every included task; `no_log`, `become` and check
  mode behaviour do not carry over unless set on the include or the tasks themselves.
- Modules and filter plugins are source-available callees: read them in the collection when
  installed; otherwise treat them as black boxes.

## Terraform

Ask these, in order, for each module or resource block:

1. **Whose viewpoint?** Inside a module, every input is untrusted. In a root module, its own
   variable values are trusted. Say which one the notes take.
2. **What actually guards this value?** Only a `validation` block or a `precondition` /
   `postcondition` counts. A `default` with no `validation` behind it guards nothing.
3. **What comes back from the provider?** The provider is opaque. List each attribute the
   code treats as computed, and where the code uses it.
4. **Can this resource be missing?** A conditional `count` or `for_each` is a path on which
   it does not exist; every reference to it must cope with that.

## GitLab CI

- Component and template `spec: inputs:` are parameters; `rules:` and `only/except` are
  branches; `needs:` and artifacts are data flow between jobs.
- Safety often rests on things outside the file: protected variables, protected branches and
  tags, runner tags, environment protection. Record each as established outside the
  repository, or `nothing found`.
- Images, `include: remote`, `include: project` from another repository and scripts fetched
  with `curl` are black boxes.
