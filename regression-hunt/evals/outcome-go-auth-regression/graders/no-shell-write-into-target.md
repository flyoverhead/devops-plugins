---
type: tool_used
tool: Bash
input_match: '(?:>>?|\btee\s+(?:-a\s+)?)\s*\\?["'']?(?:[^\s"'';&|<>]*/)?target/|\b(?:cp|mv|install|rsync)\s+(?:[^;&|\n]*?\s)?\\?["'']?(?:[^\s"'';&|<>]*/)?target/[^\s"'';&|]*\\?["'']?\s*(?:$|[;&|)]|\\n|"\s*})'
min: 0
max: 0
arm: both
---
