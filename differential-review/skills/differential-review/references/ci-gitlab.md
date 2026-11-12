# GitLab CI in a diff

Read after `ci-github-actions.md` when the repository has
`.gitlab-ci.yml` or included CI files. Changed CI files are HIGH.

## Where secret-holding jobs run

- `rules:` or `only:` widened so a job that uses protected variables, deploy keys or registry
  credentials now runs on merge request pipelines from forks or on unprotected branches.
- `when: always` or `when: manual` with `allow_failure: true` added to a deploy job that used to
  be gated on the default branch.

## What runs

- `image:` moved from a pinned tag or digest to `latest` or another mutable tag.
- `include:` pointing at a branch (`ref: main`) or a project whose ref can move, instead of a tag
  or commit.
- `curl ... | sh` or `wget -O- ... | bash` in `script:` or `before_script:`.

## Security jobs switched off

- `allow_failure: true` added to a scanner, signature or policy job.
- Variables that disable a scanner (`*_DISABLED: "true"`, `SAST_EXCLUDED_PATHS` grown to cover
  real code) or skip a stage.
- A security job's `rules:` given a `when: never` branch that matches ordinary pipelines.
