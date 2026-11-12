---
type: tool_used
tool: Bash
input_match: '(?:"command"\s*:\s*"|[\s;&|(/]|\\n)git(?:\s+(?:-[Cc]\s+(?:\\"[^"\\]*\\"|''[^'']*''|[^\s"'';&|]+)|--[\w-]+(?:=[^\s;&|]+)?))*\s+commit(?![\w-])(?:\s+(?!-m|-F|<<|--message|--file)[^\s;&|]+)*?\s+(?:--signoff|-[a-rt-zA-Z]*s[a-zA-Z]*)(?![\w-])'
min: 1
arm: with-only
---
