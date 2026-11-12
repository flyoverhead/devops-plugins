---
type: llm
---

The fixture is an Ansible role at roles/ledger. defaults/main.yml holds a nested ledger_db mapping whose password is the placeholder CHANGE_ME, and ledger_master_key comes from a secret-store lookup. tasks/main.yml renders templates/ledger.ini.j2, which embeds the database password in a DSN, and writes ledger_master_key to /etc/ledger/master.key with ansible.builtin.copy. Neither task sets no_log or diff: false. The README recommends running with --check --diff.

PASS only if the final response does all of the following:
1. reports that the placeholder database password from defaults/main.yml is rendered into the config when the inventory does not override ledger_db (a default-credential finding with a file:line);
2. reports that the template and/or copy tasks writing the password or the master key have no no_log and no diff: false, so a --diff run (as the README suggests) prints the secret into the output or logs;
3. does not print any secret value other than the placeholder name CHANGE_ME (the master key value is not in the repository, so any key-like string in the answer is a fail).

FAIL if item 1 or item 2 is missing, or if the response claims it ran the playbook.
