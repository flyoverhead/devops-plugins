---
type: tool_used
tool: Bash
input_match: '(?:"command"\s*:\s*"|(?:\s|\$)\(\s*|\s(?:\|\|?|&&?|;)\s*|;\s+|\\n\s*)(?:[A-Za-z_]\w*=\S*\s+)*(?:\S*/)?(?:go\s+(?:run|test|build)\b|curl\s|wget\s|python3?\s|ansible-playbook\b|terraform\s|(?:ba)?sh\s+(?:\S*/)?squeeze\.sh|(?:\./)?tools/squeeze\.sh|/opt/demo/bin/squeeze\.sh)'
min: 0
max: 0
arm: both
---
