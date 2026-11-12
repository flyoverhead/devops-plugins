def upper_or($d): (. // $d) | tostring | ascii_upcase;
{
  results: [
    (.results // [])[]
    | (.extra.metadata // {}) as $m
    | select(($m.category // "security" | tostring | ascii_downcase) == "security")
    | select(($m.confidence | upper_or("MEDIUM")) as $c | $c == "MEDIUM" or $c == "HIGH")
    | select(($m.impact | upper_or("MEDIUM")) as $i | $i == "MEDIUM" or $i == "HIGH")
  ],
  errors: (.errors // []),
  paths: (.paths // {})
}
