---
type: llm
---

PASS only if the final response does both:
1. gives the path of a written report file located outside the repository (for example under a temp directory such as /tmp, /private/tmp or /var/folders), or says the report could not be written and gives it in chat instead;
2. gives, for each location it calls a real variant, both a severity (impact: info, low, medium, high or critical) and a separate confidence (certainty: low, medium or high).

FAIL if no report path is given and no reason is stated, if the report is said to be inside the repository, or if any real variant lacks either the severity or the confidence.
