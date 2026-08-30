"""UserPromptSubmit: print the reply standard beside every prompt. The model reads it; the member never sees it.

Routing (deterministic, thresholds from the cardTiers knob, default "6,12"):
  a question, or longer than 12 words  -> the whole card
  6 words or fewer                     -> one line back
  anything else                        -> the Shape half only
Loop: if the meter scored the previous reply with violations, the card opens by naming them.
Never blocks a turn: every path exits 0.
"""
import datetime
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import store  # noqa: E402

CARD_PATH = pathlib.Path(__file__).resolve().parent.parent / "resources" / "card.md"
QUESTION = re.compile(r"\?|^(why|what|how|should|is|are|can|could|which|do|does|explain|tell me|help me understand)\b", re.I)
ONE_LINE = "REPLY STANDARD: one line back, action first, plain words, no preamble, no closing pleasantry."


def tiers():
    """(oneLine, full) word thresholds from the cardTiers knob, falling back to 6 and 12."""
    try:
        one, full = str(store.config("cardTiers", "6,12")).split(",")
        return int(one), int(full)
    except Exception:
        return 6, 12


def violation_prefix():
    """The line naming what the last metered reply broke, or "" when it broke nothing."""
    prev = store.last("meter.log") or {}
    broke = [f"{k.replace('_', ' ')} x{v}" for k, v in (prev.get("violations") or {}).items() if v]
    if not broke:
        return ""
    return "Your previous reply broke the standard: " + ", ".join(broke) + ". Not this time."


def card_for(prompt):
    """(mode, text) for one prompt."""
    words = len(prompt.split())
    one_line, full = tiers()
    if QUESTION.search(prompt) or words > full:
        return "full card", CARD_PATH.read_text(encoding="utf-8").strip()
    if words <= one_line:
        return "one line", ONE_LINE
    _prose, shape = CARD_PATH.read_text(encoding="utf-8").split("Shape:", 1)
    return "shape half", "REPLY STANDARD (read before you answer)\n\nShape:" + shape.rstrip()


def main():
    try:
        prompt = (json.loads(sys.stdin.buffer.read().decode("utf-8", "replace")).get("prompt") or "").strip()
    except Exception:
        prompt = ""
    sys.stdout.reconfigure(encoding="utf-8")
    prefix = violation_prefix()
    if prefix:
        print(prefix)
        print()
    try:
        mode, text = card_for(prompt)
        print(text)
    except Exception:
        mode = "none"
    store.append("card.log", {
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "prefix": prefix,
        "prompt": prompt[:80],
    })


def _self_test():
    import os
    import subprocess
    import tempfile

    def run(prompt, data):
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=data)
        env.pop("CLAUDE_PLUGIN_CONFIG", None)
        env.pop("CLAUDE_PLUGIN_CONFIG_CARDTIERS", None)
        p = subprocess.run([sys.executable, __file__], input=json.dumps({"prompt": prompt}).encode(),
                           capture_output=True, env=env)
        assert p.returncode == 0, p.stderr
        return p.stdout.decode()

    with tempfile.TemporaryDirectory() as tmp:
        out = run("fix the tests", tmp)
        assert out.strip() == ONE_LINE, out

        out = run("rewrite the parser and update its callers", tmp)
        assert out.startswith("REPLY STANDARD (read before you answer)") and "Shape:" in out, out
        assert "Prose:" not in out, out

        out = run("why does the parser drop the last token?", tmp)
        assert "Prose:" in out and "Shape:" in out, out

        assert store.last.__module__  # store is importable
        os.environ["CLAUDE_PLUGIN_DATA"] = tmp
        log = store.last("card.log")
        assert log["mode"] == "full card" and log["prefix"] == "", log

        store.append("meter.log", {"violations": {"long_paragraph": 2, "no_next_action": 0}})
        out = run("fix the tests", tmp)
        assert out.startswith("Your previous reply broke the standard: long paragraph x2. Not this time."), out
        assert ONE_LINE in out, out
    print("card.py self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
    sys.exit(0)
