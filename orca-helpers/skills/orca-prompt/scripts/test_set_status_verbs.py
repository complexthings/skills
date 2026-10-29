#!/usr/bin/env python3
"""Self-check for set_status.py's item verb dispatch. Run: python3 test_set_status_verbs.py"""
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import set_status
from test_set_status import make_workstream, run, status


def note(workstream_dir, item_id, args):
    """A throwaway verb: `<id> note <text>` stores text on the item."""
    if len(args) != 1:
        raise set_status.StatusError("usage: set_status.py <workstream-dir> <id> note <text>")
    s = set_status._read_json(Path(workstream_dir) / set_status.STATUS_FILE)
    next(i for i in s["items"] if i["id"] == item_id)["note"] = args[0]
    set_status._write(workstream_dir, s)


def cli(*args):
    """Run main() in-process, the way __main__ does, so a registered verb is visible."""
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            set_status.main(list(args))
            code = 0
        except set_status.StatusError as e:
            print(f"FAIL: {e}")
            code = 1
    return code, out.getvalue()


def test_registered_verb_gets_dir_id_and_args_and_writes_atomically():
    calls = []
    set_status.VERBS["note"] = lambda d, i, a: (calls.append((d, i, a)), note(d, i, a))
    try:
        with tempfile.TemporaryDirectory() as root:
            d = make_workstream(root)
            run(str(d), "--start")
            assert cli(str(d), "02-b", "note", "hello") == (0, "")
            assert calls == [(str(d), "02-b", ["hello"])]
            assert {i["id"]: i for i in status(d)["items"]}["02-b"]["note"] == "hello"
            assert [p.name for p in d.iterdir() if p.name.startswith(".status-")] == []
            before = (d / "_status.json").read_bytes()
            code, out = cli(str(d), "02-b", "note")
            assert code == 1 and out.startswith("FAIL:") and out.count("\n") == 1, out
            assert (d / "_status.json").read_bytes() == before
    finally:
        del set_status.VERBS["note"]


def test_unknown_verb_fails_once_and_leaves_file_untouched():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        before = (d / "_status.json").read_bytes()
        for args in (("01-a", "bogus"), ("01-a", "bogus", "x", "y", "z")):
            r = run(str(d), *args)
            assert r.returncode == 1, args
            assert r.stdout.startswith("FAIL:") and r.stdout.count("\n") == 1, (args, r.stdout)
        assert (d / "_status.json").read_bytes() == before


def test_a_verb_never_shadows_a_state():
    set_status.VERBS["complete"] = lambda *a: (_ for _ in ()).throw(AssertionError("shadowed"))
    try:
        with tempfile.TemporaryDirectory() as root:
            d = make_workstream(root)
            run(str(d), "--start")
            assert cli(str(d), "01-a", "complete")[0] == 0
            assert status(d)["items"][0]["state"] == "complete"
    finally:
        del set_status.VERBS["complete"]



def test_review_report_supplies_the_verdict_and_unsigned_is_no_ship():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        item = lambda: {i["id"]: i for i in status(d)["items"]}["02-b"]
        report = Path(root) / "report.md"
        report.write_text("# Review\n\nNone.\n\nVERDICT: SHIP\n\n")
        assert cli(str(d), "02-b", "review", "1", "codex", "--report", str(report)) == (0, "")
        assert (item()["state"], item()["review"]["verdict"]) == ("reviewing", "SHIP")
        # A VERDICT line that is not the last line does not sign the report.
        report.write_text("VERDICT: SHIP\nmore findings\n")
        for rnd in ("1", "2", "3"):
            assert cli(str(d), "02-b", "review", rnd, "codex", "--report", str(report))[0] == 0
            assert item()["review"]["verdict"] == "NO-SHIP"
        assert (item()["state"], item()["reason"]) == ("failed", "review: 3 NO-SHIP rounds")
        report.write_text("")
        assert cli(str(d), "01-a", "review", "1", "codex", "--report", str(report))[0] == 0
        assert status(d)["items"][0]["review"]["verdict"] == "NO-SHIP"
        before = (d / "_status.json").read_bytes()
        code, out = cli(str(d), "01-a", "review", "1", "codex", "--report", str(Path(root) / "missing.md"))
        assert code == 1 and out.startswith("FAIL:") and out.count("\n") == 1, out
        assert (d / "_status.json").read_bytes() == before


def test_run_and_task_verbs_refuse_bad_input():
    with tempfile.TemporaryDirectory() as root:
        d = make_workstream(root)
        run(str(d), "--start")
        before = (d / "_status.json").read_bytes()
        for args in (("run",), ("run", "a", "b"), ("01-a", "task"), ("zz", "task", "t1")):
            code, out = cli(str(d), *args)
            assert code == 1 and out.startswith("FAIL:") and out.count("\n") == 1, (args, out)
        assert (d / "_status.json").read_bytes() == before
        assert cli(str(d), "run", "run_1") == (0, "")
        assert cli(str(d), "01-a", "task", "task_1") == (0, "")
        s = status(d)
        assert s["runId"] == "run_1" and s["items"][0]["taskId"] == "task_1"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
