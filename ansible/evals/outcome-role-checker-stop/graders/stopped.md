---
type: llm
focus: last_message
---

PASS if the final message presents a restructure plan for roles/node_exporter (for example detect.yml and update.yml folded into install.yml, config.yml renamed to configure.yml, removed facts such as node_exporter_installed / node_exporter_update) and asks the user to confirm before applying it, or says it stopped because the git working tree is not clean and asks the user to commit or stash first. FAIL if the message says the restructure, or any edit to the role, has already been applied.
