def table_for($run; $r):
  $r.rule.toolComponent.index as $c
  | (if ($c | type) == "number" then $run.tool.extensions[$c] else $run.tool.driver end)
  | .rules // [];
def rule_for($run; $r):
  table_for($run; $r) as $table
  | ([$r.rule.index, $r.ruleIndex] | map(numbers) | first) as $at
  | if $at != null and $at >= 0 and $at < ($table | length) then $table[$at]
    else first($table[] | select(.id == ($r.ruleId // $r.rule.id))) // null end;
def important($rule):
  ($rule.properties // {}) as $p
  | ($p.precision // "unknown") as $precision
  | ($p["security-severity"] // 0 | tostring | tonumber? // 0) as $severity
  | if $precision == "medium" then $severity >= 6.0
    else ["high", "very-high", "unknown"] | index($precision) != null end;
.runs |= map(. as $run | .results = [(.results // [])[] | select(important(rule_for($run; .)))])
