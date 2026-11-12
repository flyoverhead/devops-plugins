import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT.joinpath("skills", "audit")
REFS = SKILL_DIR.joinpath("references")
ROW = re.compile(r"^\|\s*`([a-z][a-z-]*)`\s*\|\s*([^|]+?)\s*\|")
LABEL = re.compile(r"^\*\*(.+)\*\*\s*$")
FENCE = re.compile(r"^```(\w*)\s*$")
PERL_ONLY = ("\\s", "\\d", "\\b")


def categories():
    rows = {}
    for line in (SKILL_DIR / "SKILL.md").read_text().splitlines():
        m = ROW.match(line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def load_seed_file(cid):
    with open(REFS.joinpath(cid + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def seeds(cid):
    return load_seed_file(cid)["seeds"]


def examples(md_text):
    section, label, lang, buf, inside = "", None, None, [], False
    for line in md_text.splitlines():
        if inside:
            if line.startswith("```"):
                yield section, label, lang, "\n".join(buf) + "\n"
                inside, label, buf = False, None, []
            else:
                buf.append(line)
            continue
        if line.startswith("## "):
            section = line[3:].strip().lower()
            label = None
        elif LABEL.match(line):
            label = LABEL.match(line).group(1)
        elif FENCE.match(line) and label:
            lang, inside = FENCE.match(line).group(1), True


def corpus(cid):
    return list(examples((REFS / f"{cid}.md").read_text()))


CATS = categories()


def test_skill_table_has_rows():
    assert CATS, "no category rows found in SKILL.md"


def test_reference_stems_match_categories():
    stems = set()
    for entry in REFS.iterdir():
        if entry.suffix in {".md", ".json"}:
            stems.add(entry.stem)
    assert stems == set(CATS)
    for cid in CATS:
        assert (REFS / f"{cid}.json").is_file() and (REFS / f"{cid}.md").is_file(), cid


@pytest.mark.parametrize("cid", sorted(CATS))
def test_seed_file(cid):
    data = load_seed_file(cid)
    assert data["id"] == cid
    assert data["title"] == CATS[cid]
    assert data["seeds"], f"{cid} has no seeds"
    for s in data["seeds"]:
        assert not any(tok in s for tok in PERL_ONLY), f"{cid}: non-POSIX escape in {s}"


@pytest.mark.parametrize("cid", sorted(CATS))
def test_corpus_shape(cid):
    text = (REFS / f"{cid}.md").read_text()
    assert re.search(r"^# \S", text, re.M), "missing H1"
    assert re.search(r"^\*\*Report when:\*\*", text, re.M), "missing Report-when line"
    assert re.search(r"^\*\*Skip when:\*\*", text, re.M), "missing Skip-when line"
    vulnerable = [e for e in corpus(cid) if "vulnerable" in e[0]]
    assert vulnerable, f"{cid}: no vulnerable examples"


ALL_SEEDS = []
for _cid in CATS:
    ALL_SEEDS.extend(seeds(_cid))
VULNERABLE = [(cid, label, code) for cid in CATS
              for section, label, _, code in corpus(cid) if "vulnerable" in section]


@pytest.mark.skipif(shutil.which("grep") is None, reason="not run: grep missing")
@pytest.mark.parametrize("cid,label,code", VULNERABLE, ids=[f"{c}:{l}" for c, l, _ in VULNERABLE])
def test_vulnerable_example_is_seeded(cid, label, code, tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text(code)
    for s in ALL_SEEDS:
        r = subprocess.run(["grep", "-Eq", "-e", s, str(sample)], capture_output=True, text=True)
        assert r.returncode in (0, 1), f"grep failed on seed {s!r}: {r.stderr}"
        if r.returncode == 0:
            return
    pytest.fail(f"{cid}: no seed matches example {label!r}")


def test_stack_coverage():
    langs = {lang for cid in CATS for _, _, lang, _ in corpus(cid)}
    for need in ("go", "bash", "hcl", "yaml"):
        assert need in langs, f"no {need} example in any corpus"


def test_workflow_example_present():
    labels = [label for _, label, _ in VULNERABLE]
    assert any(re.search(r"github actions|workflow", l, re.I) for l in labels)


@pytest.mark.skipif(shutil.which("grep") is None, reason="not run: grep missing")
def test_every_seed_matches_a_vulnerable_example(tmp_path):
    sample = tmp_path / "all.txt"
    sample.write_text("".join(code for _, _, code in VULNERABLE))
    idle = [s for s in ALL_SEEDS
            if subprocess.run(["grep", "-Eq", "-e", s, str(sample)]).returncode != 0]
    assert not idle, f"seeds with no vulnerable example: {idle}"
