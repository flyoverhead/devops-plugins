---
type: regex
target: trace
---

^(?:(?![^\n]*"type":"tool_use","id":"[^"]*","name":"(?:Write|Edit|NotebookEdit)")(?![^\n]*"type":"tool_use","id":"[^"]*","name":"Bash","input":\{"command":"[^"\n]*\b(?:git (?:mv|rm)|mv|rm) [^"\n]*node_exporter)[^\n]*\n)*\{"type":"assistant"(?=[^\n]*"type":"text","text":"[^\n]*update\.yml)(?=[^\n]*"type":"text","text":"[^\n]*configure\.yml)(?=[^\n]*"type":"text","text":"[^\n]*argument_specs)(?=[^\n]*"type":"text","text":"[^\n]*node_exporter_(?:installed|update)\b)
