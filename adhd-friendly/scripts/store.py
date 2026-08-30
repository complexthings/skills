"""The one place that knows where adhd-friendly state lives.

Data directory: ${CLAUDE_PLUGIN_DATA}, else ~/.claude/adhd-friendly/. Created on demand.
Hook scripts import append/last/config so none of them repeats path logic.
Nothing here raises at a hook: append and last swallow their own errors.
"""
import json
import os
import pathlib
import sys

FALLBACK = pathlib.Path.home() / ".claude" / "adhd-friendly"


def data_dir():
    """The directory logs live in, created if missing."""
    d = pathlib.Path(os.environ.get("CLAUDE_PLUGIN_DATA") or FALLBACK).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


def append(name, record):
    """Append one JSON line to the named log. Returns True when written."""
    try:
        with (data_dir() / name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except Exception:
        return False


def tail(name, n=50):
    """The last n JSON lines of the named log, oldest first. Unreadable lines are skipped."""
    rows = []
    try:
        lines = (data_dir() / name).read_text(encoding="utf-8").splitlines()
    except Exception:
        return rows
    for line in lines[-n:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def last(name):
    """The last JSON line of the named log, or None when there is nothing to read."""
    rows = tail(name, 1)
    return rows[-1] if rows else None


def config(key, default=None):
    """One userConfig knob. Reads the CLAUDE_PLUGIN_CONFIG JSON blob, else CLAUDE_PLUGIN_CONFIG_<KEY>."""
    try:
        blob = json.loads(os.environ.get("CLAUDE_PLUGIN_CONFIG") or "{}")
        if key in blob:
            return blob[key]
    except Exception:
        pass
    raw = os.environ.get("CLAUDE_PLUGIN_CONFIG_" + key.upper())
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _tail_check():
    """tail returns oldest-first, caps at n, and survives a corrupt line."""
    assert tail("missing.log") == []
    assert tail("card.log") == [{"n": 1}, {"n": 2}]
    assert tail("card.log", 1) == [{"n": 2}]
    with (data_dir() / "card.log").open("a", encoding="utf-8") as f:
        f.write("not json\n")
    assert tail("card.log") == [{"n": 1}, {"n": 2}]
    return True


def _self_test():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["CLAUDE_PLUGIN_DATA"] = tmp + "/nested"
        assert data_dir().is_dir()
        assert last("card.log") is None
        assert append("card.log", {"n": 1})
        assert append("card.log", {"n": 2})
        assert last("card.log") == {"n": 2}
        assert _tail_check()

        os.environ.pop("CLAUDE_PLUGIN_CONFIG", None)
        os.environ.pop("CLAUDE_PLUGIN_CONFIG_METER", None)
        assert config("meter", True) is True
        os.environ["CLAUDE_PLUGIN_CONFIG_METER"] = "false"
        assert config("meter", True) is False
        os.environ["CLAUDE_PLUGIN_CONFIG"] = json.dumps({"strictness": "strict"})
        assert config("strictness", "normal") == "strict"
        assert config("cardTiers", "6,12") == "6,12"
    print("store.py self-test ok")


if __name__ == "__main__" and "--self-test" in sys.argv:
    _self_test()
