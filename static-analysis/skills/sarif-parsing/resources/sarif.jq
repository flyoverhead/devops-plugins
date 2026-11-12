def sarif_rules($run; $r):
  $r.rule.toolComponent.index as $c
  | (if ($c | type) == "number" then $run.tool.extensions[$c] else $run.tool.driver end)
  | .rules // [];
def sarif_rule($run; $r):
  sarif_rules($run; $r) as $table
  | ([$r.rule.index, $r.ruleIndex] | map(numbers) | first) as $at
  | if $at != null and $at >= 0 and $at < ($table | length) then $table[$at]
    else first($table[] | select(.id == ($r.ruleId // $r.rule.id))) // null end;
def sarif_level($run; $r):
  if (($r | has("kind")) and $r.kind != "fail") then "none"
  else [$r.level, sarif_rule($run; $r).defaultConfiguration.level, "warning"] | map(strings) | first end;
def sarif_results:
  .runs[]? as $run | ($run.results // [])[] | . + {_level: sarif_level($run; .)};
