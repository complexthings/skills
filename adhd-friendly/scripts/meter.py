"""Stop hook: score the reply that just finished, write one JSON line to meter.log. Silent, never blocks, always exits 0.

The STE counters are SimpleEnglish's ste_lint.py (AminBlg/SimpleEnglish, MIT), unchanged in what they count, plus the
house spelling and dash counts. The ADHD shape counters live beside the STE total, never inside it: a reply can be
perfect Simple English and still be a wall of text. A regex pass, not a grammar parser: the same for every reply.

strictness knob: "lenient" scores shape only, "normal" adds the STE set, "strict" also folds the house counts in.
meter knob: false means log nothing.
"""
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import store  # noqa: E402

BANNED_MODALS = re.compile(r"\b(should|would|may|might|could)\b", re.I)
PERFECT = re.compile(r"\b(has|have|had)\s+been\b|\b(has|have)\s+\w+ed\b", re.I)
CONTRACTION = re.compile(r"\b\w+(n't|'ll|'re|'ve|'d)\b|\bit's\b|\byou're\b", re.I)
ING_CLAUSE = re.compile(r",\s*(mak|allow|enabl|ensur|highlight|creat|provid|offer|help|reduc|improv|lead|caus|result)ing\b", re.I)
LATIN = re.compile(r"\b(e\.g\.|i\.e\.|etc\.?)(?=[\s,)]|$)", re.I)
SLOP = re.compile(
    r"\b(simply|seamlessly|effortlessly|robust|leverag\w*|utiliz\w*|"
    r"comprehensive|powerful|blazingly|streamlin\w*|facilitat\w*|"
    r"performant|plethora|myriad|delve|crucial|pivotal)\b", re.I)
TRAILING_COND = re.compile(r"\w[^.!?\n]{3,}\s\b(if|when)\b\s", re.I)
ROTATION_SETS = [
    ("check-verify", re.compile(r"\b(check|verify|confirm|validate|ensure)\w*\b", re.I)),
    ("config-settings", re.compile(r"\b(config|configuration|settings)\b", re.I)),
]
# ours
AMERICAN = re.compile(
    r"\b(\w+iz(e|es|ed|ing|ation|ations)|colors?|behaviors?|favors?|centers?|analyz(e|ed|ing)|catalog)\b", re.I)
DASH = re.compile("[—–]| -- ")
LIMITS = {"procedural": 20, "descriptive": 25}

# ADHD shape
LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+[.)])\s+\S")
BOLD = re.compile(r"\*\*[^*\n]+\*\*")
MAX_LIST_ITEMS = 5
MAX_PARAGRAPH_WORDS = 50
NEXT_ACTION = re.compile(
    r"`[^`]+`"
    r"|\bnext\b\s*:"
    r"|^\s*(?:\*\*)?(?:\d+[.)]\s*)?(?:then\s+|now\s+|first\s+)?"
    r"(run|open|try|read|write|check|add|edit|start|copy|paste|click|type|send|commit|push|install|"
    r"delete|rename|reply|pick|choose|tell|ask|set|fix|move|apply|rerun|re-run|deploy|merge)\b", re.I)


def strip_code(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`\n]+`", " CODESPAN ", text)  # one word per Rule 8.6
    text = re.sub(r"^#+\s.*$", " ", text, flags=re.M)  # headings exempt (titles, 8.6)
    text = re.sub(r"https?://\S+", " URL ", text)
    return text


def sentences(text):
    text = re.sub(r"^\s*([-*]|\d+\.)\s+", "", text, flags=re.M)  # list markers
    parts = re.split(r"(?<=[.!?:])\s+", text)
    return [p.strip() for p in parts if len(p.strip().split()) >= 2]


def list_blocks(text):
    """Runs of consecutive list lines, each as its list of leading-indent widths."""
    blocks, current = [], []
    for line in text.splitlines():
        m = LIST_ITEM.match(line)
        if m:
            current.append(len(m.group(1).expandtabs(4)))
        elif line.strip() == "" and current:
            continue  # a blank line inside a list does not end it
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def shape(text):
    """The ADHD counters, reported beside the STE total and never inside it."""
    body = strip_code(text)
    blocks = list_blocks(body)
    over_five = sum(1 for b in blocks if len(b) > MAX_LIST_ITEMS)
    deep = 0
    for b in blocks:
        indents = sorted({i for i in b if i > 0})
        unit = indents[0] if indents else 0
        if unit and max(b) // unit > 1:
            deep += 1
    paragraphs = [
        p for p in re.split(r"\n\s*\n", body)
        if p.strip() and not all(LIST_ITEM.match(l) or not l.strip() for l in p.splitlines())
    ]
    lines = [l for l in text.strip().splitlines() if l.strip()]
    return {
        "reply_words": len(text.split()),
        "list_over_5": over_five,
        "list_nested_deep": deep,
        "bold_markers": len(BOLD.findall(body)),
        "paragraph_over_50w": sum(1 for p in paragraphs if len(p.split()) > MAX_PARAGRAPH_WORDS),
        "ends_with_next_action": bool(lines and NEXT_ACTION.search(lines[-1])),
    }


def lint(text, text_type="descriptive", strictness="normal"):
    body = strip_code(text)
    sents = sentences(body)
    limit = LIMITS[text_type]
    counts = {}
    lengths = [len(s.split()) for s in sents]
    counts["sentence_over_limit"] = sum(1 for n in lengths if n > limit)
    counts["contraction"] = len(CONTRACTION.findall(body))
    counts["banned_modal"] = len(BANNED_MODALS.findall(body))
    counts["perfect_tense"] = len([m for m in PERFECT.finditer(body)])
    counts["ing_clause"] = len(ING_CLAUSE.findall(body))
    counts["semicolon"] = body.count(";")
    counts["latin_abbrev"] = len(LATIN.findall(body))
    counts["slop_word"] = len(SLOP.findall(body))
    counts["trailing_condition"] = sum(
        1 for s in sents if TRAILING_COND.search(s) and not re.match(r"^(if|when)\b", s, re.I))
    rotation = 0
    for _, rx in ROTATION_SETS:
        stems = {m.group(1).lower().rstrip("s") for m in rx.finditer(body)}
        if len(stems) > 1:
            rotation += len(stems) - 1
    counts["synonym_rotation"] = rotation
    words = max(1, len(body.split()))
    house = {"american_spelling": len(AMERICAN.findall(body)), "dash": len(DASH.findall(body))}
    ste_total = 0 if strictness == "lenient" else sum(counts.values())
    if strictness == "strict":
        ste_total += sum(house.values())
    return {
        "type": text_type,
        "strictness": strictness,
        "words": words,
        "sentences": len(sents),
        "mean_sentence_words": round(sum(lengths) / max(1, len(lengths)), 1),
        "longest_sentence_words": max(lengths, default=0),
        "violations": counts,
        "violations_total": ste_total,
        "violations_per_100w": round(100.0 * ste_total / words, 2),
        "house": house,
        "shape": shape(text),
    }


def main():
    if not store.config("meter", True):
        return
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    text = data.get("last_assistant_message") or ""
    if not text.strip():
        return
    row = lint(text, "descriptive", str(store.config("strictness", "normal")))
    row["session_id"] = data.get("session_id")
    store.append("meter.log", row)


def _self_test():
    import tempfile

    clean = "Run the migration.\nOpen the log after."
    r = lint(clean)
    assert r["violations_total"] == 0, r["violations"]
    assert r["shape"]["ends_with_next_action"] is True
    assert r["shape"]["list_over_5"] == 0
    assert r["shape"]["bold_markers"] == 0

    # one reply breaking each new ADHD counter
    bad = (
        "- a\n- b\n- c\n- d\n- e\n- f\n"
        "\n"
        "- top\n  - one\n    - two\n"
        "\n"
        "**bold one** and **bold two**\n"
        "\n"
        + " ".join(["word"] * 60) + "\n"
        "\nSo that is the state of things.\n"
    )
    s = lint(bad)["shape"]
    assert s["list_over_5"] == 1, s
    assert s["list_nested_deep"] == 1, s
    assert s["bold_markers"] == 2, s
    assert s["paragraph_over_50w"] == 1, s
    assert s["ends_with_next_action"] is False, s
    assert s["reply_words"] > 60, s

    # empty reply: never raises, scores nothing
    e = lint("")
    assert e["violations_total"] == 0 and e["sentences"] == 0
    assert e["shape"]["reply_words"] == 0
    assert e["shape"]["ends_with_next_action"] is False

    # code blocks stay exempt
    assert lint("```\nshould might color;\n```\nRun it.")["violations_total"] == 0

    # strictness knobs
    loud = "This should have been simplified; e.g. the color."
    assert lint(loud, strictness="lenient")["violations_total"] == 0
    normal = lint(loud, strictness="normal")["violations_total"]
    assert normal > 0
    assert lint(loud, strictness="strict")["violations_total"] > normal

    # the hook path: writes one line, prints nothing, exits 0
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CLAUDE_PLUGIN_DATA"] = tmp
        os.environ["CLAUDE_PLUGIN_CONFIG"] = json.dumps({"meter": True, "strictness": "normal"})
        store.append("meter.log", lint("Run it.")) and None
        assert store.last("meter.log")["shape"]["ends_with_next_action"] is True
        os.environ["CLAUDE_PLUGIN_CONFIG"] = json.dumps({"meter": False})
        assert store.config("meter", True) is False
    print("meter.py self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        try:
            main()
        except Exception:
            pass
        sys.exit(0)
