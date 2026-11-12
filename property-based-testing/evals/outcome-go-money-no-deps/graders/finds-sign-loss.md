---
type: llm
---

The user asked for property tests of Format and Parse (cents <-> decimal text) and a report of what they found. The code has one real defect: Format drops the minus sign for amounts between -1 and -99 cents (-5 renders as "0.05"), so Parse(Format(c)) != c, although Format's doc comment promises that Parse inverts it for every int64.

PASS only if the final response:
1. says the roundtrip property failed (or that a property test exposed a failure), and names a concrete cause: the sign is lost for small negative amounts, or an equivalent description with a concrete failing value such as -1, -5 or -99;
2. treats it as a code bug (or a violation of the documented guarantee), not as a mistake in the test;
3. does not claim to have changed amount.go.

Extra findings beyond this defect do not matter.

FAIL if it says every property passes, blames the test, or claims it fixed Format.
