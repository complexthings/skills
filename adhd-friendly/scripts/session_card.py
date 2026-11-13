"""SessionStart: two lines of state carried over from the last session.

The only hook here that the member ever sees. It prints what the logs record and nothing else:
the last prompt the card fired on, and the last reply the meter scored. Empty logs print nothing.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402


def lines(card, meter):
    """The at-most-two state lines, given the last card.log and meter.log rows."""
    out = []
    prompt = " ".join(((card or {}).get("prompt") or "").split())
    if prompt:
        out.append("Last session was working on: " + prompt[:80])
    if meter:
        broke = [f"{k.replace('_', ' ')} x{v}" for k, v in (meter.get("violations") or {}).items() if v]
        words = meter.get("words")
        tail = f", {words} words" if words else ""
        out.append("Last reply scored: " + (", ".join(broke) if broke else "clean") + tail + ".")
    return out


def main():
    sys.stdin.read()  # drain the hook payload; nothing in it is needed
    for line in lines(store.last("card.log"), store.last("meter.log")):
        print(line)
    return 0


def _self_test():
    assert lines(None, None) == []
    assert lines({}, None) == []
    assert lines({"prompt": "  fix the  meter hook "}, None) == ["Last session was working on: fix the meter hook"]
    assert lines(None, {"violations": {}, "words": 40}) == ["Last reply scored: clean, 40 words."]
    got = lines({"prompt": "ship it"}, {"violations": {"slop_word": 2, "semicolon": 0}, "words": 310})
    assert got == ["Last session was working on: ship it", "Last reply scored: slop word x2, 310 words."], got
    assert lines({"prompt": "x" * 200}, {"violations": {}})[0].endswith("x" * 80)
    print("session_card.py self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        try:
            sys.exit(main())
        except Exception:
            sys.exit(0)
