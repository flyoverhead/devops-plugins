#!/usr/bin/env python3
"""Structural checks for a mutation-testing-report.md written on the faregate eval fixture."""
import argparse
import re
import sys
from pathlib import Path

MIN_CHARS = 500
SURVIVOR_LINES = (23, 24, 25, 32, 33, 36, 42, 47)
NOT_TIER_ONE_LINES = (24, 36, 47)
HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
TABLE_RULE = re.compile(r"^\|?[ \t]*:?-{3,}:?[ \t]*(\|[ \t]*:?-{3,}:?[ \t]*)*\|?[ \t]*$")
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.M | re.S)
GE_ZERO = re.compile(r">=\s*0(?!\d)")
NE_ZERO = re.compile(r"!=\s*0(?!\d)")


class ReportError(Exception):
    """The text is not shaped like a report at all."""


def headings(text):
    fenced = [m.span() for m in FENCE.finditer(text)]
    return [m for m in HEADING.finditer(text)
            if not any(a <= m.start() < b for a, b in fenced)]


def sections(text):
    """Return (title, start, stop); a section runs to the next heading at the same or a higher level."""
    found = headings(text)
    result = []
    for idx, head in enumerate(found):
        depth = len(head.group(1))
        stop = len(text)
        for later in found[idx + 1:]:
            if len(later.group(1)) <= depth:
                stop = later.start()
                break
        result.append((head.group(2), head.start(), stop))
    return result


def is_equivalent_heading(title):
    low = title.lower()
    return ("equivalent" in low
            and not re.search(r"\bnot[\s-]+equivalent|\bnon-?equivalent|\binequivalent", low)
            and not re.search(r"summary|distribution", low))


def merge(spans):
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def cells(row):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def mutated_sides(block):
    """(text, exact) per data row of each table in block.

    exact is True when the table has a header cell mentioning "mutat": the text is then that cell
    after its last arrow. Otherwise the text is the whole row."""
    sides = []
    column = None
    lines = [ln.strip() for ln in block.splitlines()]
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            column = None
            continue
        if TABLE_RULE.match(line):
            continue
        if i + 1 < len(lines) and TABLE_RULE.match(lines[i + 1]):
            column = next((k for k, c in enumerate(cells(line)) if "mutat" in c.lower()), None)
            continue
        row = cells(line)
        if column is None or column >= len(row):
            sides.append((line, False))
        else:
            sides.append((re.split(r"→|->", row[column])[-1], True))
    return sides


def cites_line(text, n):
    gap = r"(?:\W{1,6}|\s+(?:and|or|to)\s+)"
    pattern = (rf"\blines?\W{{1,6}}(?:\d+{gap})*{n}(?!\d)"
               rf"|\|\s*{n}\s*\|"
               rf"|\.\w+:{n}(?!\d)")
    return re.search(pattern, text, re.I) is not None


def check(text):
    if not headings(text):
        raise ReportError("report has no section headings at all")
    parts = sections(text)
    spans = merge([(a, b) for title, a, b in parts if is_equivalent_heading(title)])
    if not spans:
        raise ReportError("cannot find a section about equivalent mutants")

    problems = []
    if len(text.strip()) < MIN_CHARS:
        problems.append(f"report is a stub ({len(text.strip())} characters, need {MIN_CHARS})")

    sides = mutated_sides("\n".join(text[a:b] for a, b in spans))
    if not sides:
        problems.append("equivalent-mutants section has no table rows")
    if any(GE_ZERO.search(s) and (exact or not NE_ZERO.search(s)) for s, exact in sides):
        problems.append("`>= 0` on line 42 is listed as equivalent, but it differs at rides_left == 0")
    if not any(NE_ZERO.search(s) for s, _ in sides):
        problems.append("`!= 0` on line 42 is not listed as equivalent, though u32 makes it so")

    outside, cursor = [], 0
    for a, b in spans:
        outside.append(text[cursor:a])
        cursor = b
    outside.append(text[cursor:])
    if not GE_ZERO.search("".join(outside)):
        problems.append("`>= 0` is never discussed as a real gap outside the equivalent section")

    tier_one = [text[a:b] for title, a, b in parts if re.search(r"tier\s*1|critical", title, re.I)
                and not re.search(r"summary|distribution", title, re.I)]
    if not tier_one:
        problems.append("no Tier 1 / Critical section")
    else:
        body = "\n".join(tier_one)
        if "blocked" not in body.lower():
            problems.append("Tier 1 does not name the blocked-card guard")
        for word in ("served", "queue_open"):
            if word in body:
                problems.append(f"Tier 1 mentions `{word}`, which belongs in a lower tier")
        for n in NOT_TIER_ONE_LINES:
            if cites_line(body, n):
                problems.append(f"Tier 1 cites line {n}, which belongs in a lower tier")

    for n in SURVIVOR_LINES:
        if not cites_line(text, n):
            problems.append(f"survivor on line {n} is never cited")
    return problems


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Check a mutation-testing-report.md for the faregate fixture.",
        epilog="exit 0: checks pass (with --expect-fail: report rejected as it should be); "
               "1: checks fail (with --expect-fail: report accepted); 2: usage or read error")
    parser.add_argument("report", type=Path)
    parser.add_argument("--expect-fail", action="store_true",
                        help="the report is known to be wrong; succeed only if it is rejected")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        raw = args.report.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"unreadable report {args.report} ({exc})\n")
        return 2
    try:
        problems = check(text)
    except ReportError as exc:
        problems = [str(exc)]

    if args.expect_fail:
        if problems:
            print(f"{args.report}: rejected as expected")
            for p in problems:
                print(f"  * {p}")
            return 0
        print(f"{args.report}: accepted a report that should fail; the checks have no teeth",
              file=sys.stderr)
        return 1
    if problems:
        print(f"{args.report}: {len(problems)} problem(s)", file=sys.stderr)
        for p in problems:
            print(f"  * {p}", file=sys.stderr)
        return 1
    print(f"valid: {args.report} (survivor lines {len(SURVIVOR_LINES)}/8 cited; "
          "line 42 split into one equivalent and one gap; blocked-card guard in Tier 1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
