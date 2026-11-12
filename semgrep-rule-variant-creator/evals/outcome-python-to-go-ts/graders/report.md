---
type: llm
---

Fixture facts: sast/flask-os-system/ holds a Python taint rule (source flask.request.args.get / form.get, sinks os.system and subprocess shell=True, sanitizer shlex.quote) and its test file. The user asked for ports to Go and TypeScript under rules/.

PASS only if the final response does all of the following:
1. names two separate variant directories, one for Go and one for TypeScript, each named from the original id plus the language (for example flask-os-system-go and flask-os-system-typescript or -ts), and each with a rule YAML and a test file whose extension matches the language;
2. reports a `semgrep --test` outcome per language (passed, or the failures that remain);
3. the Go variant targets a shell command string (for example exec.Command with "sh" "-c") built from net/http request data, and the TypeScript variant targets child_process exec or execSync built from request data such as an Express req.query; neither is a literal translation of `os.system`;
4. mentions the Semgrep version used.

Any other response FAILs, in particular one that drops a language, folds both into a single directory, or leaves a language without a stated test result.
