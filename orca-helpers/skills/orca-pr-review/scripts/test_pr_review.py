#!/usr/bin/env python3
"""Self-check for pr_review.py. Run: python3 test_pr_review.py"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import pr_review

ME = "greg"


def pr(number=1, author="ana", assignees=(), state="OPEN", head="aaa"):
    """`gh pr view --json` output for one PR."""
    return {
        "number": number, "title": f"PR {number}", "url": f"https://github.com/o/r/pull/{number}",
        "state": state, "author": {"login": author}, "assignees": [{"login": a} for a in assignees],
        "headRefOid": head, "baseRefName": "main", "headRefName": f"feat-{number}",
    }


def entry(verdict=None, head=None):
    return {"number": 1, "title": "PR 1", "url": "u", "author": "ana", "claimedAt": "t",
            "headSha": head, "round": 1 if verdict else 0, "verdict": verdict, "worker": None, "draft": None}


def test_classify():
    c = lambda p, e=None: pr_review.classify(p, ME, e)
    assert c(pr(author=ME)) == "UNSUPPORTED"
    assert c(pr(author=ME, assignees=[ME])) == "UNSUPPORTED"
    assert c(pr(assignees=["bo"])) == "CLAIMED"
    assert c(pr(assignees=["bo"]), entry()) == "CLAIMED"
    assert c(pr()) == "NEW"
    assert c(pr(assignees=[ME])) == "NEW"
    assert c(pr(assignees=[ME, "bo"])) == "NEW"
    assert c(pr(assignees=[ME]), entry()) == "INFLIGHT"
    assert c(pr(assignees=[ME], head="bbb"), entry("CHANGES_REQUESTED", "aaa")) == "FOLLOWUP"
    assert c(pr(assignees=[ME], head="aaa"), entry("CHANGES_REQUESTED", "aaa")) == "IDLE"
    assert c(pr(assignees=[ME], head="bbb"), entry("APPROVED", "aaa")) == "IDLE"
    assert c(pr(state="MERGED")) == "IDLE"
    assert c(pr(state="CLOSED", assignees=[ME]), entry()) == "IDLE"
    # Merged after my REQUEST_CHANGES: no round 2, only cleanup.
    assert c(pr(state="MERGED", assignees=[ME], head="bbb"), entry("CHANGES_REQUESTED", "aaa")) == "IDLE"
    # A round 2 in progress (verdict cleared, head recorded) is INFLIGHT, not another FOLLOWUP.
    assert c(pr(assignees=[ME], head="bbb"), {**entry(), "round": 2, "since": "aaa", "headSha": "bbb"}) == "INFLIGHT"


class FakeGh:
    """Answers `gh` like GitHub would, with `rival` adding itself between my view and my edit."""

    def __init__(self, assignees=(), rival=None):
        self.assignees, self.rival, self.calls = list(assignees), rival, []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("pr", "view"):
            return json.dumps({"assignees": [{"login": a} for a in self.assignees]})
        if "--add-assignee" in args:
            if self.rival:
                self.assignees.append(self.rival)
            self.assignees.append(args[-1])
        if "--remove-assignee" in args:
            self.assignees.remove(args[-1])
        return ""


def edits(fake):
    return [a for a in fake.calls if a[:2] == ("pr", "edit")]


def test_claim():
    fake = FakeGh()
    assert pr_review.claim("o/r", 1, ME, run=fake) and fake.assignees == [ME]
    # Someone else assigned: no edit at all.
    fake = FakeGh(["bo"])
    assert not pr_review.claim("o/r", 1, ME, run=fake) and edits(fake) == []
    # Already mine: no edit.
    fake = FakeGh([ME])
    assert pr_review.claim("o/r", 1, ME, run=fake) and edits(fake) == []
    # Race lost to a lower login: back off and remove myself.
    fake = FakeGh(rival="ana")
    assert not pr_review.claim("o/r", 1, ME, run=fake) and fake.assignees == ["ana"]
    # Race won against a higher login: keep it.
    fake = FakeGh(rival="zed")
    assert pr_review.claim("o/r", 1, ME, run=fake) and sorted(fake.assignees) == [ME, "zed"]


def test_settings_defaults():
    with tempfile.TemporaryDirectory() as data:
        assert pr_review.settings_for(data, "o/r") == pr_review.DEFAULTS
        assert pr_review.DEFAULTS["mode"] == "manual" and pr_review.DEFAULTS["cadenceMinutes"] == 5
        assert pr_review.loop_cadence(data) == 5
        (Path(data) / "review-settings.json").write_text(json.dumps({
            "o/r": {"watched": True, "mode": "auto", "cadenceMinutes": 15}, "o/s": {"gifs": True, "cadenceMinutes": 1}}))
        assert pr_review.settings_for(data, "o/r") == {**pr_review.DEFAULTS, "watched": True, "mode": "auto", "cadenceMinutes": 15}
        assert pr_review.settings_for(data, "o/s")["gifs"] is True
        # Only a Watched Repo sets the cron cadence.
        assert pr_review.loop_cadence(data) == 15
        (Path(data) / "review-settings.json").write_text("not json")
        assert pr_review.settings_for(data, "o/r")["mode"] == "manual"


def watching(data, *repos):
    """Make `repos`, o/r by default, Watched Repos."""
    pr_review.save_settings(data, {r: {"watched": True} for r in repos or ["o/r"]})
    return data


def fake_github(prs, search, posted=None):
    """A `gh` stand-in for a tick: `prs` maps number to view JSON, `search` lists open numbers in o/r,
    and each review POST lands in `posted` as (path, payload)."""
    def run(*args):
        if args[:3] == ("api", "-X", "POST"):
            posted.append((args[3], json.loads(Path(args[-1]).read_text())))
            return "{}"
        if args[:2] == ("api", "-H"):
            return f"diff --git a/a.py b/a.py\n+fixed at {args[3].rsplit('/', 1)[-1]}\n"
        if args[:2] == ("api", "user"):
            return ME + "\n"
        if args[:2] == ("search", "prs"):
            return json.dumps([{"repository": {"nameWithOwner": "o/r"}, "number": n} for n in search])
        if args[:2] == ("pr", "view"):
            p = prs[int(args[2])]
            return json.dumps(p if "assignees" not in args[-1:] else {"assignees": p["assignees"]})
        if args[:2] == ("pr", "edit"):
            prs[int(args[2])]["assignees"].append({"login": args[-1]})
            return ""
        raise AssertionError(args)
    return run


class FakeOrca:
    """Answers the `orca` calls a tick makes. Records each worker-start spec, and each cleanup
    step in `cleaned`. `workers` maps a dispatch id to the worker-show fields a test sets."""

    def __init__(self, fail=None, cleanup_fail=None):
        self.specs, self.argv, self.fail, self.cleanup_fail = [], [], fail, cleanup_fail
        self.workers, self.cleaned, self.sent, self.gone, self.requests = {}, [], [], set(), []
        self.rm_fail = 0

    def __call__(self, *args):
        if args[:2] == ("orchestration", "worker-show") and args[3] in self.gone:
            raise pr_review.Fail("`orca orchestration worker-show` exited 1: dispatch_not_found: "
                                 f"Worker Dispatch {args[3]} was not found.")
        if args[:2] == ("orchestration", "worker-show"):
            w = {"status": "dispatched", "activity": "working", "lastOutputAt": 0, "agentWait": None,
                 "liveness": "live", **self.workers.get(args[3], {})}
            # The field paths a live Orca 1.4.243 worker-show --json answers with.
            return json.dumps({"ok": True, "result": {
                "dispatch": {"id": args[3], "runId": "run_1", "status": w["status"]},
                "worker": {"worktreeId": f"repo-1::/wt/{args[3]}"},
                "projection": {"stage": {"activity": w["activity"]}},
                "observation": {"agentWait": w["agentWait"]},
                "terminal": {"lastOutputAt": w["lastOutputAt"]}}})
        if args[:2] == ("orchestration", "worker-list"):
            # Liveness lives on the worker-list row, paged: the last row sits on a second page.
            assert args[3] == "run_1", args
            rows = [{"dispatchId": d, "projection": {"liveness": {"verdict": w.get("liveness", "live")}}}
                    for d, w in self.workers.items()]
            first = "--cursor" not in args
            return json.dumps({"ok": True, "result": {"workers": rows[:-1] if first else rows[-1:],
                                                      "page": {"hasMore": first, "nextCursor": "c2" if first else None}}})
        if args[:2] in (("orchestration", "worker-stop"), ("orchestration", "worker-release"), ("worktree", "rm")):
            if self.cleanup_fail:
                raise pr_review.Fail(self.cleanup_fail)
            if args[:2] == ("worktree", "rm") and self.rm_fail:
                self.rm_fail -= 1
                raise pr_review.Fail("`orca worktree rm` exited 1: busy")
            self.cleaned.append(args[:2] + (args[3],))
            return "{}"
        if args[:2] == ("orchestration", "send"):
            self.sent.append((args[3], args[args.index("--body") + 1]))
            return "{}"
        assert args[:2] == ("orchestration", "worker-start"), args
        self.requests.append(args[args.index("--retry-request") + 1])
        if self.fail:
            raise self.fail if isinstance(self.fail, Exception) else pr_review.Fail(self.fail)
        self.argv.append(args)
        self.specs.append(args[args.index("--spec") + 1])
        return json.dumps({"ok": True, "result": {"dispatch": {"dispatchId": f"ctx_{len(self.specs)}"}}})


def cleanup_of(handle, stopped=True):
    """The cleanup calls FakeOrca records for review worker `handle`: release before `worktree rm`, never `terminal close`."""
    tree = f"id:repo-1::/wt/{handle}"
    return ([("orchestration", "worker-stop", handle)] if stopped else []) + [
        ("orchestration", "worker-release", handle), ("worktree", "rm", tree)]


def stub_orca(fake, clone="/nowhere"):
    pr_review.orca = fake
    pr_review.orca_repo = lambda repo: {"id": "repo-1", "path": clone}
    return fake


def test_tick():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs = {1: pr(1), 2: pr(2, assignees=["bo"]), 3: pr(3, author=ME)}
        lines = []
        pr_review.gh = fake_github(prs, [1, 2, 3])
        orca = stub_orca(FakeOrca())
        # The loop started in a repo with no Prompt Settings, so the worker runs on Claude Code.
        pr_review._write(pr_review._loop_file(data), {"repoPath": data})
        pr_review.tick(data, out=lines.append)
        assert lines == ["Claimed o/r#1: PR 1. https://github.com/o/r/pull/1",
                         "UNSUPPORTED-evidence o/r: its Review Settings set no evidenceCommand, so each review brief "
                         "says Evidence Record: none. Add evidenceCommand to o/r in review-settings.json to run one.",
                         "Reviewing o/r#1: a review worker started in its own worktree."]
        assert "- Evidence Record: none: no evidence command is set" in orca.specs[0]
        led = pr_review.read_ledger(data, "o/r")
        assert list(led["prs"]) == ["1"] and led["prs"]["1"]["verdict"] is None and led["scannedAt"]
        assert led["prs"]["1"]["worker"] == "ctx_1" and led["prs"]["1"]["round"] == 1
        assert led["prs"]["1"]["harness"] == "claude" and led["evidenceReported"] is True
        # The repo is not due again inside its cadence, and a due quiet tick prints nothing.
        lines.clear()
        pr_review.tick(data, out=lines.append)
        assert lines == []
        led["scannedAt"] = "2000-01-01T00:00:00+00:00"
        pr_review._write(pr_review.ledger_path(data, "o/r"), led)
        pr_review.tick(data, out=lines.append)
        assert lines == []
        # A tracked PR that left the search (merged) is still read, and stays quiet.
        prs[1]["state"] = "MERGED"
        led = pr_review.read_ledger(data, "o/r")
        led["scannedAt"] = None
        pr_review._write(pr_review.ledger_path(data, "o/r"), led)
        pr_review.gh = fake_github(prs, [2, 3])
        pr_review.tick(data, out=lines.append)
        assert lines == []


def write_draft(data, number, draft, rnd=1):
    path, _ = pr_review.review_paths(data, "o/r", number, rnd)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft))
    return path


def due(data):
    """Make o/r due for a scan again, so the next tick reads it inside the same test."""
    led = pr_review.read_ledger(data, "o/r")
    led["scannedAt"] = None
    pr_review._write(pr_review.ledger_path(data, "o/r"), led)


DRAFT = {"event": "REQUEST_CHANGES", "body": "Changes requested: 1 blocking finding.\nThe parser is tidy.",
         "comments": [{"path": "a.py", "line": 3, "body": "Off by one."}]}


def test_manual_holds_then_approve_posts():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs, posted, lines = {1: pr(1)}, [], []
        pr_review.gh = fake_github(prs, [1], posted)
        orca = stub_orca(FakeOrca())
        pr_review.tick(data, out=lines.append)
        # The worker runs in its own worktree on the PR's base, and its spec names both output paths.
        argv = orca.argv[0]
        assert argv[argv.index("--worktree") + 1] == "new-top-level" and argv[argv.index("--base-branch") + 1] == "main"
        draft_file, report = pr_review.review_paths(data, "o/r", 1, 1)
        assert str(draft_file) in orca.specs[0] and str(report) in orca.specs[0] and "Demonstrated Failure" in orca.specs[0]
        # No draft yet: the worker is still reviewing, and the tick is quiet.
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == [] and pr_review.classify(prs[1], ME, pr_review.read_ledger(data, "o/r")["prs"]["1"]) == "INFLIGHT"
        # The draft lands: manual mode holds it, says so once, and posts nothing.
        write_draft(data, 1, DRAFT)
        due(data)
        pr_review.tick(data, out=lines.append)
        assert len(lines) == 1 and lines[0].startswith("Review Draft ready for o/r#1: REQUEST_CHANGES.")
        assert "/orca-pr-review approve o/r#1" in lines[0] and posted == []
        entry = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert entry["draft"] == str(draft_file) and entry["verdict"] is None and entry["headSha"] == "aaa"
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == [] and posted == []
        # Approve posts it against the reviewed commit and records the verdict.
        pr_review.approve(data, "o/r#1", out=lines.append)
        assert lines == ["Posted o/r#1: CHANGES_REQUESTED, 1 inline comments. https://github.com/o/r/pull/1"]
        path, payload = posted[0]
        assert path == "repos/o/r/pulls/1/reviews" and payload["commit_id"] == "aaa" and payload["event"] == "REQUEST_CHANGES"
        assert payload["comments"] == [{"path": "a.py", "line": 3, "side": "RIGHT", "body": "Off by one."}]
        entry = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert entry["verdict"] == "CHANGES_REQUESTED"
        assert pr_review.classify(prs[1], ME, entry) == "IDLE"
        assert pr_review.classify({**prs[1], "headRefOid": "bbb"}, ME, entry) == "FOLLOWUP"
        # A second approve has nothing to post.
        try:
            pr_review.approve(data, "o/r#1")
            assert False
        except pr_review.Fail as e:
            assert "no Review Draft waits for o/r#1" in str(e)


def test_auto_posts_and_claimed_pr_drops():
    with tempfile.TemporaryDirectory() as data:
        (Path(data) / "review-settings.json").write_text(json.dumps({"o/r": {"watched": True, "mode": "auto"}}))
        prs, posted, lines = {1: pr(1), 2: pr(2)}, [], []
        pr_review.gh = fake_github(prs, [1, 2], posted)
        orca = stub_orca(FakeOrca())
        pr_review.tick(data, out=lines.append)
        write_draft(data, 1, {"event": "APPROVE", "body": "Approved: 0 blocking findings.\nClear tests."})
        write_draft(data, 2, DRAFT)
        # Someone else takes PR 2 while I review it: its draft is dropped, never posted.
        prs[2]["assignees"] = [{"login": "bo"}]
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == ["Posted o/r#1: APPROVED, 0 inline comments. https://github.com/o/r/pull/1",
                         "Dropped the Review Draft for o/r#2: bo took the PR."]
        assert [p for p, _ in posted] == ["repos/o/r/pulls/1/reviews"]
        # Both workers are cleaned up: the posted one and the dropped one.
        assert sorted(orca.cleaned) == sorted(cleanup_of("ctx_1") + cleanup_of("ctx_2"))
        led = pr_review.read_ledger(data, "o/r")
        assert led["prs"]["1"]["verdict"] == "APPROVED" and "2" not in led["prs"]
        assert not pr_review.review_paths(data, "o/r", 2, 1)[0].exists()
        assert pr_review.classify(prs[2], ME, None) == "CLAIMED"


def test_followup_reviews_only_the_new_commits():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs, posted, lines = {1: pr(1)}, [], []
        pr_review.gh = fake_github(prs, [1], posted)
        orca = stub_orca(FakeOrca())
        pr_review.tick(data, out=lines.append)
        write_draft(data, 1, DRAFT)
        pr_review.review_paths(data, "o/r", 1, 1)[1].write_text("## Findings\n\n- `a.py:3`: off by one.\n")
        due(data); pr_review.tick(data, out=lines.append)
        pr_review.approve(data, "o/r#1", out=lines.append)
        # Posting cleans up round 1's worker, worktree and terminals.
        assert orca.cleaned == cleanup_of("ctx_1")
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["worker"] is None
        # The author pushes: round 2 starts and its brief carries only aaa...bbb plus the round 1 findings.
        prs[1]["headRefOid"] = "bbb"
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == ["Round 2 for o/r#1: new commits since my REQUEST_CHANGES at aaa.",
                         "Reviewing o/r#1: a review worker started in its own worktree."]
        spec = orca.specs[1]
        assert "- Round: 2, a follow-up: review only the changes since aaa" in spec
        assert "## Changes since round 1" in spec and "+fixed at aaa...bbb" in spec
        assert "## Earlier findings\n\n## Findings\n\n- `a.py:3`: off by one." in spec
        assert str(pr_review.review_paths(data, "o/r", 1, 2)[0]) in spec
        assert "Changes since round" not in orca.specs[0]
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert (e["round"], e["since"], e["headSha"], e["verdict"], e["worker"]) == (2, "aaa", "bbb", None, "ctx_2")
        # Round 2 approves: it posts against the new head, and an unchanged head stays IDLE.
        write_draft(data, 1, {"event": "APPROVE", "body": "Approved: 0 blocking findings.\nThe fix is tight."}, rnd=2)
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        pr_review.approve(data, "o/r#1", out=lines.append)
        assert posted[-1][1]["commit_id"] == "bbb" and posted[-1][1]["event"] == "APPROVE"
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and len(orca.specs) == 2


def test_cleanup_after_merge_or_close():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs, lines = {1: pr(1)}, []
        pr_review.gh = fake_github(prs, [1])
        orca = stub_orca(FakeOrca(cleanup_fail="`orca worktree rm` exited 1: busy"))
        pr_review.tick(data, out=lines.append)
        # Merged mid-review: cleanup runs, a failure prints once and retries.
        prs[1]["state"] = "MERGED"
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == ["Cleanup failed for o/r#1: `orca worktree rm` exited 1: busy. The next tick retries."]
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and pr_review.read_ledger(data, "o/r")["prs"]["1"]["worker"] == "ctx_1"
        orca.cleanup_fail = None
        due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and orca.cleaned == cleanup_of("ctx_1")
        # Cleaned up, the merged PR keeps its entry with finishedAt and state, and is never read again:
        # a gh with no PR 1 raises KeyError on any `pr view`.
        entry = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert entry["state"] == "MERGED" and datetime.fromisoformat(entry["finishedAt"]) and entry["title"] == "PR 1"
        pr_review.gh = fake_github({}, [])
        due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and pr_review.read_ledger(data, "o/r")["prs"]["1"] == entry
        assert pr_review.candidates(data) == []
        # Even a search hit for a finished PR is not read again.
        pr_review.gh = fake_github({}, [1])
        due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and pr_review.candidates(data) == []
        lines.clear(); pr_review.status(data, out=lines.append)
        assert lines == ["Loop: stopped.", "No PRs in the ledger."]
        # A settled dispatch is not stopped again, only released and its worktree removed.
        orca.workers["ctx_9"] = {"status": "completed"}
        orca.cleaned.clear()
        pr_review.cleanup({"worker": "ctx_9"})
        assert orca.cleaned == cleanup_of("ctx_9", stopped=False)


def test_stuck_worker_is_restarted():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs, lines = {1: pr(1)}, []
        pr_review.gh = fake_github(prs, [1])
        orca = stub_orca(FakeOrca())
        pr_review.tick(data, out=lines.append)
        long_ago = 0
        just_now = pr_review.datetime.now(pr_review.timezone.utc).timestamp() * 1000
        # Idle briefly, or waiting on a human: healthy, left alone.
        for w in ({"activity": "idle", "lastOutputAt": just_now}, {"activity": "idle", "agentWait": {"kind": "prompt"}}):
            orca.workers["ctx_1"] = w
            lines.clear(); due(data); pr_review.tick(data, out=lines.append)
            assert lines == [] and len(orca.specs) == 1 and orca.cleaned == []
        # Idle at its prompt past STUCK_AFTER with no draft: stopped, cleaned up, dispatched again.
        orca.workers["ctx_1"] = {"activity": "idle", "lastOutputAt": long_ago}
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert len(lines) == 2 and lines[0].startswith("Restarted the review worker for o/r#1: it sat idle at its prompt for ")
        assert lines[1] == "Reviewing o/r#1: a review worker started in its own worktree."
        assert orca.cleaned == cleanup_of("ctx_1") and len(orca.specs) == 2
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert (e["worker"], e["restarts"], e["round"]) == ("ctx_2", 1, 1)
        # A worker that settled or exited with no draft is restarted too, then the loop gives up and says so once.
        orca.workers["ctx_2"] = {"status": "completed"}
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines[0] == "Restarted the review worker for o/r#1: its dispatch is completed with no Review Draft."
        orca.workers["ctx_3"] = {"liveness": "exited"}
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == ["The review worker for o/r#1 is stuck again: its agent exited. It was restarted 2 times this round. "
                         "Read it with `orca orchestration worker-read --dispatch ctx_3`."]
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and len(orca.specs) == 3


def held(data, mode="manual"):
    """A PR o/r#1 whose round 1 Review Draft is held, its worker ctx_1 still in its worktree."""
    (Path(data) / "review-settings.json").write_text(json.dumps({"o/r": {"watched": True, "mode": mode}}))
    prs, posted, lines = {1: pr(1)}, [], []
    pr_review.gh = fake_github(prs, [1], posted)
    orca = stub_orca(FakeOrca())
    pr_review.tick(data, out=lines.append)
    write_draft(data, 1, DRAFT)
    if mode == "manual":
        due(data); pr_review.tick(data, out=lines.append)
    return prs, posted, orca


def test_feedback_to_a_live_worker():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data)
        lines = []
        pr_review.feedback(data, "O/R#1", "  Drop the off-by-one finding: line 3 is right. ", out=lines.append)
        assert lines == ["Sent your Review Feedback to the review worker for o/r#1. The next tick holds its rewritten "
                         "Review Draft for **/orca-pr-review approve o/r#1**."]
        # The live worker gets the feedback and the draft it answers; no second worker starts.
        (to, body), = orca.sent
        assert to == "dispatch:ctx_1" and len(orca.specs) == 1
        assert "Drop the off-by-one finding: line 3 is right.\n" in body and '"Off by one."' in body
        draft_file = pr_review.review_paths(data, "o/r", 1, 1)[0]
        assert str(draft_file) in body and not draft_file.exists()
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert (e["draft"], e["worker"], e["verdict"]) == (None, "ctx_1", None) and e["feedback"].startswith("Drop")
        # Until the rewrite lands, nothing waits for approve.
        try:
            pr_review.approve(data, "o/r#1")
            assert False
        except pr_review.Fail as err:
            assert "no Review Draft waits for o/r#1" in str(err)
        write_draft(data, 1, {"event": "APPROVE", "body": "Approved: 0 blocking findings.\nClean parser."})
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert len(lines) == 1 and lines[0].startswith("Review Draft ready for o/r#1: APPROVE.") and posted == []


def test_feedback_to_a_stopped_worker_starts_a_fresh_one_on_its_worktree():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data)
        # The author pushed since: the rewrite still reviews the commit the draft reviewed.
        prs[1]["headRefOid"] = "ccc"
        orca.workers["ctx_1"] = {"status": "completed"}
        lines = []
        pr_review.feedback(data, "o/r#1", "Say why the parser change is safe.", out=lines.append)
        assert lines == ["Started a fresh review worker for o/r#1 with your Review Feedback: the old one its dispatch is "
                         "completed with no Review Draft. The next tick holds its rewritten Review Draft for "
                         "**/orca-pr-review approve o/r#1**."]
        argv, spec = orca.argv[1], orca.specs[1]
        assert argv[argv.index("--worktree") + 1] == "id:repo-1::/wt/ctx_1" and orca.sent == []
        assert not {"--repo", "--base-branch", "--name"} & set(argv)
        assert "## Review Feedback" in spec and "Say why the parser change is safe." in spec and '"Off by one."' in spec
        assert "- Head commit to review: aaa" in spec
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert (e["worker"], e["draft"], e["headSha"]) == ("ctx_2", None, "aaa")
        # A failed start puts the held draft back and leaves the ledger as it was.
        orca.fail = "`orca orchestration worker-start` exited 1: busy"
        write_draft(data, 1, DRAFT)
        led = pr_review.read_ledger(data, "o/r"); led["prs"]["1"]["draft"] = str(pr_review.review_paths(data, "o/r", 1, 1)[0])
        pr_review._write(pr_review.ledger_path(data, "o/r"), led)
        orca.workers["ctx_2"] = {"status": "failed"}
        try:
            pr_review.feedback(data, "o/r#1", "Again.")
            assert False
        except pr_review.Fail:
            pass
        assert pr_review.review_paths(data, "o/r", 1, 1)[0].exists()
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["worker"] == "ctx_2"


def test_feedback_to_a_worker_orca_forgot_starts_a_fresh_one_on_its_worktree():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data)
        orca.gone.add("ctx_1")
        lines = []
        pr_review.feedback(data, "o/r#1", "Say why the parser change is safe.", out=lines.append)
        assert lines[0].startswith("Started a fresh review worker for o/r#1 with your Review Feedback: "
                                   "Orca no longer knows the old one.")
        # With no worker-show to name its worktree id, the worktree's name finds it.
        argv = orca.argv[1]
        assert argv[argv.index("--worktree") + 1] == "name:review-r-1" and orca.cleaned == [] and orca.sent == []
        assert not {"--repo", "--base-branch", "--name"} & set(argv)
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["worker"] == "ctx_2"


def test_run_names_the_orca_error_code():
    err = json.dumps({"ok": False, "error": {"code": "dispatch_not_found", "message": "gone"}})
    try:
        pr_review._run(sys.executable, ["-c", f"import sys; print({err!r}); sys.exit(1)"], 5)
        assert False
    except pr_review.Fail as e:
        assert str(e).endswith("exited 1: dispatch_not_found: gone"), e


def test_feedback_without_a_held_draft_fails():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        real = pr_review.plugin_data_dir
        pr_review.plugin_data_dir = lambda: Path(data)
        run = lambda *argv: (pr_review.main(["pr_review.py", *argv]), buf.getvalue().splitlines()[-1])
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                # No ledger entry, a malformed target, and text as an argument all fail with one FAIL: line.
                sys.stdin = io.StringIO("Fix it.")
                assert run("feedback", "o/r#1") == (
                    1, "FAIL: no Review Draft waits for o/r#1. Run `pr_review.py status` to list the ledger")
                assert run("feedback", "o/r#x")[0] == 1
                code, last = run("feedback", "o/r#1", "Fix", "it.")
                assert code == 1 and last.startswith("FAIL: usage:")
        finally:
            pr_review.plugin_data_dir, sys.stdin = real, sys.__stdin__
        held(data)
        try:
            pr_review.feedback(data, "o/r#1", "   ")
            assert False
        except pr_review.Fail as e:
            assert "Review Feedback is empty" in str(e)
        assert pr_review.review_paths(data, "o/r", 1, 1)[0].exists()


def test_feedback_text_comes_on_stdin():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data)
        real = pr_review.plugin_data_dir
        pr_review.plugin_data_dir = lambda: Path(data)
        # Quotes, `$` and backticks reach the worker as written: nothing passes through a shell.
        text = 'Drop "the nit" on $HOME and `x`.\nKeep the rest.'
        sys.stdin = io.StringIO(text + "\n")
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                assert pr_review.main(["pr_review.py", "feedback", "o/r#1"]) == 0
        finally:
            pr_review.plugin_data_dir, sys.stdin = real, sys.__stdin__
        assert buf.getvalue().startswith("Sent your Review Feedback to the review worker for o/r#1.")
        (to, body), = orca.sent
        assert text in body and pr_review.read_ledger(data, "o/r")["prs"]["1"]["feedback"] == text


def test_feedback_rewrite_stays_held_in_auto_mode():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data, mode="auto")
        # Auto mode posts a draft at once, so hold one the way a tick does not: mark it picked up, unposted.
        led = pr_review.read_ledger(data, "o/r")
        led["prs"]["1"]["draft"] = str(pr_review.review_paths(data, "o/r", 1, 1)[0])
        pr_review._write(pr_review.ledger_path(data, "o/r"), led)
        pr_review.feedback(data, "o/r#1", "Request changes on a.py:3 only.", out=lambda line: None)
        write_draft(data, 1, DRAFT)
        lines = []
        for _ in range(2):
            due(data); pr_review.tick(data, out=lines.append)
        assert posted == [] and len(lines) == 1 and lines[0].startswith("Review Draft ready for o/r#1: REQUEST_CHANGES.")
        pr_review.approve(data, "o/r#1", out=lines.append)
        assert [p for p, _ in posted] == ["repos/o/r/pulls/1/reviews"]
        # The next round posts in auto mode again.
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert e["verdict"] == "CHANGES_REQUESTED"
        prs[1]["headRefOid"] = "bbb"
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["feedback"] is None


def test_bad_draft_and_dispatch_errors_print_once():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs, lines = {1: pr(1)}, []
        pr_review.gh = fake_github(prs, [1])
        # A lost reply (timeout) prints once, then the next tick replays the start with the same retry id.
        lost = stub_orca(FakeOrca(fail=pr_review.Fail("`orca orchestration worker-start` timed out after 300s", timed_out=True)))
        pr_review.tick(data, out=lines.append)
        assert lines[-1] == "No review worker for o/r#1: `orca orchestration worker-start` timed out after 300s. The next tick retries."
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == [] and len(lost.requests) == 2 and lost.requests[0] == lost.requests[1]
        replay = stub_orca(FakeOrca())
        due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == ["Reviewing o/r#1: a review worker started in its own worktree."]
        assert replay.requests == lost.requests[:1]
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["startRequest"] is None
        write_draft(data, 1, {"event": "LGTM"})
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert len(lines) == 1 and "not postable: event must be one of" in lines[0]
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["draft"] is None
        lines.clear(); due(data)
        pr_review.tick(data, out=lines.append)
        assert lines == []


def test_evidence_record_runs_once_on_the_pr_head():
    git = lambda *a: pr_review._run("git", list(a), 30).strip()
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as data:
        src, origin, clone = (Path(tmp) / n for n in ("src", "origin.git", "clone"))
        git("init", "-q", str(src))
        (src / "f.txt").write_text("from the head\n")
        git("-C", str(src), "add", "f.txt")
        git("-C", str(src), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "head")
        sha = git("-C", str(src), "rev-parse", "HEAD")
        git("init", "-q", "--bare", str(origin))
        git("-C", str(src), "push", "-q", str(origin), "HEAD:refs/pull/1/head", "HEAD:refs/heads/main")
        git("clone", "-q", str(origin), str(clone))
        (Path(data) / pr_review.SETTINGS_FILE).write_text(json.dumps({"o/r": {"watched": True, "evidenceCommand": "cat f.txt; exit 3"}}))
        prs, lines = {1: pr(1, head=sha)}, []
        pr_review.gh = fake_github(prs, [1])
        orca = stub_orca(FakeOrca(), clone)
        pr_review.tick(data, out=lines.append)
        # A non-zero exit is evidence too, and a repo with an evidence command prints no UNSUPPORTED-evidence line.
        assert not any("UNSUPPORTED-evidence" in line for line in lines)
        assert f"- Evidence Record: commit {sha}, in the section below" in orca.specs[0]
        assert f"## Evidence Record\n\n````text\nEvidence Record, commit {sha}, exit 3\nfrom the head\n````" in orca.specs[0]
        # The temporary checkout is gone: the clone lists only its own worktree.
        assert git("-C", str(clone), "worktree", "list").count("\n") == 0


def test_review_payload_bodies():
    # REQUEST_CHANGES with no inline comments and no body carries a one-line body.
    p = pr_review.review_payload({"event": "REQUEST_CHANGES", "body": "  ", "comments": []}, "sha")
    assert p["body"] == "Changes requested." and "\n" not in p["body"] and p["comments"] == []
    assert pr_review.review_payload({"event": "APPROVE"}, "sha")["body"] == ""
    assert pr_review.review_payload(DRAFT, "sha")["body"] == DRAFT["body"]
    assert pr_review.draft_problem(DRAFT) is None
    assert pr_review.draft_problem({**DRAFT, "comments": [{"path": "a", "line": 0, "body": "x"}]})


def test_worker_harness():
    with tempfile.TemporaryDirectory() as repo:
        assert pr_review.worker_harness(repo) == {"name": "claude"}
        settings = Path(repo) / ".orca" / "prompts" / "prompt-settings.json"
        settings.parent.mkdir(parents=True)
        codex = {"name": "codex", "models": {"orchestrationWorker": {"model": "gpt-6.1-sol", "effort": "high"}}}
        settings.write_text(json.dumps({"harnesses": [{"name": "claude"}, codex], "mainOrchestratorHarness": "codex"}))
        h = pr_review.worker_harness(repo)
        assert h == codex and pr_review.launch_flags(h) == " --model gpt-6.1-sol --effort high"


def test_gh_timeout():
    real = pr_review.subprocess.run
    def slow(*a, **kw):
        assert kw["timeout"] == pr_review.GH_TIMEOUT and kw["stdin"] == pr_review.subprocess.DEVNULL
        raise pr_review.subprocess.TimeoutExpired(a[0], kw["timeout"])
    pr_review.subprocess.run = slow
    try:
        try:
            GH("search", "prs")
            assert False
        except pr_review.Fail as e:
            assert "timed out" in str(e)
    finally:
        pr_review.subprocess.run = real


def test_lifecycle():
    real, pr_review._terminal = pr_review._terminal, lambda: "term_loop"
    with tempfile.TemporaryDirectory() as data:
        lines = []
        pr_review.start(data, ["o/r"], out=lines.append)
        assert lines == ["CRON */5 * * * *"]
        # The Board's Review Draft jump switches to the terminal start ran in.
        assert json.loads((Path(data) / "pr-review" / "loop.json").read_text())["terminal"] == "term_loop"
        runs = json.loads((Path(data) / "runs.json").read_text())["runs"]
        assert [(r["workstream"], r["kind"]) for r in runs] == [("orca-pr-review", "pr-review")]
        pr_review.set_cron(data, "job-1", out=lines.append)
        lines.clear()
        pr_review.start(data, ["o/r"], out=lines.append)
        assert lines[:2] == ["RUNNING cron=job-1", "CRON */5 * * * *"] and lines[2].startswith("Watching o/r: a scan every 5 min")
        assert len(json.loads((Path(data) / "runs.json").read_text())["runs"]) == 1
        lines.clear()
        pr_review.stop(data, out=lines.append)
        assert lines == ["CRON job-1", "The loop has stopped. **/orca-pr-review start** starts it again."]
        lines.clear()
        pr_review.status(data, out=lines.append)
        assert lines == ["Loop: stopped.", "No PRs in the ledger."]
    pr_review._terminal = real


def test_gif_picker():
    shipped = [g["url"] for g in json.loads(pr_review.GIFS_FILE.read_text())]
    assert len(shipped) > pr_review.RECENT_GIFS and len(set(shipped)) == len(shipped)
    assert all(u.startswith("https://media.giphy.com/media/") for u in shipped)
    with tempfile.TemporaryDirectory() as data:
        picks = [pr_review.pick_gif(data, ok=lambda u: True)["url"] for _ in range(60)]
        assert set(picks) <= set(shipped)
        assert all(p not in picks[max(0, i - 10):i] for i, p in enumerate(picks))
        # A non-200 URL is skipped: only the one URL that answers is picked.
        live = next(u for u in shipped if u not in picks[-10:])
        assert pr_review.pick_gif(data, ok=lambda u: u == live)["url"] == live
        # Nothing answers: no GIF, and the recent list stays as it was.
        before = (Path(data) / "pr-review" / "gifs-used.json").read_text()
        assert pr_review.pick_gif(data, ok=lambda u: False) is None
        assert (Path(data) / "pr-review" / "gifs-used.json").read_text() == before


def test_gifs_off_by_default_and_last_line_when_on():
    assert pr_review.settings_for(tempfile.gettempdir(), "o/r")["gifs"] is False
    for gifs in (False, True):
        with tempfile.TemporaryDirectory() as data:
            (Path(data) / "review-settings.json").write_text(json.dumps({"o/r": {"watched": True, "mode": "auto", "gifs": gifs}}))
            prs, posted = {1: pr(1)}, []
            pr_review.gh = fake_github(prs, [1], posted)
            stub_orca(FakeOrca())
            pr_review.gif_ok = lambda u: True
            pr_review.tick(data, out=lambda _: None)
            write_draft(data, 1, DRAFT)
            due(data)
            pr_review.tick(data, out=lambda _: None)
            last = posted[0][1]["body"].splitlines()[-1]
            assert last.startswith("![") == gifs
            if gifs:
                used = json.loads((Path(data) / "pr-review" / "gifs-used.json").read_text())
                assert last.endswith(f"({used[-1]})")


def test_unwatched_repo_is_never_a_candidate():
    with tempfile.TemporaryDirectory() as data:
        calls = []
        def run(*args):
            calls.append(args)
            return json.dumps([{"repository": {"nameWithOwner": r}, "number": 1} for r in ("o/r", "o/x")])
        pr_review.gh = run
        # No Watched Repo: nothing is searched at all.
        assert pr_review.candidates(data) == [] and calls == []
        watching(data)
        # o/x is known but unwatched, and its ledger still tracks a PR.
        pr_review.save_settings(data, {"o/x": {"mode": "auto"}})
        pr_review._write(pr_review.ledger_path(data, "o/x"), {"repo": "o/x", "prs": {"7": entry()}})
        assert pr_review.candidates(data) == [("o/r", 1)]
        assert all(c[c.index("--repo") + 1] == "o/r" and c.count("--repo") == 1 for c in calls)


def test_watched_repo_matches_without_case():
    with tempfile.TemporaryDirectory() as data:
        watching(data, "Acme/Api")
        pr_review.gh = lambda *a: json.dumps([{"repository": {"nameWithOwner": "acme/api"}, "number": 3}])
        assert pr_review.candidates(data) == [("Acme/Api", 3)]


def test_every_spelling_hits_the_saved_key():
    real = pr_review.repo_slug, pr_review._terminal
    pr_review.repo_slug, pr_review._terminal = lambda path, host="": "acme/api", lambda: None
    with tempfile.TemporaryDirectory() as data:
        settings = Path(data) / pr_review.SETTINGS_FILE
        pr_review.save_settings(data, {"Acme/Api": {"watched": True, "mode": "auto", "loopEndHours": 3.0}})
        # start with the git remote's lowercase spelling keeps the saved key and its settings.
        pr_review.start(data, ["acme/api"], out=lambda line: None)
        assert pr_review.watched_repos(data) == ["Acme/Api"] and list(json.loads(settings.read_text())) == ["Acme/Api"]
        assert pr_review.settings_for(data, "acme/api")["mode"] == "auto"
        end = datetime.fromisoformat(json.loads(pr_review._loop_file(data).read_text())["loopEnd"])
        assert end - datetime.now(timezone.utc) > timedelta(hours=2)
        # A user typing any case: show, watch and unwatch use the saved key, and watch saves no second entry.
        lines = []
        pr_review.show(data, "ACME/API", out=lines.append)
        assert lines[0] == "SAVED Acme/Api" and "auto mode" in lines[1]
        pr_review.watch(data, "acme/API", ["gifs=true"], out=lines.append)
        saved = json.loads(settings.read_text())
        assert list(saved) == ["Acme/Api"] and saved["Acme/Api"]["mode"] == "auto" and saved["Acme/Api"]["gifs"]
        # The ledger: any spelling reads and writes one file under the saved key.
        pr_review._write(pr_review.ledger_path(data, "acme/api"), {"repo": "acme/api", "prs": {"7": entry()}})
        assert pr_review.ledger_path(data, "ACME/api") == pr_review.ledger_path(data, "Acme/Api")
        assert pr_review.read_ledger(data, "ACME/API")["repo"] == "Acme/Api"
        assert [led["repo"] for led in pr_review.all_ledgers(data)] == ["Acme/Api"]
        # gh nameWithOwner in another case still maps to the saved key.
        pr_review.gh = lambda *a: json.dumps([{"repository": {"nameWithOwner": "ACME/api"}, "number": 3}])
        assert pr_review.candidates(data) == [("Acme/Api", 3), ("Acme/Api", 7)]
        stub_orca(FakeOrca())
        pr_review.unwatch(data, "acme/api", out=lines.append)
        assert pr_review.watched_repos(data) == [] and list(json.loads(settings.read_text())) == ["Acme/Api"]
        # An unsaved repo keeps the spelling it was given.
        assert pr_review.repo_key(data, "New/Repo") == "New/Repo"
    pr_review.repo_slug, pr_review._terminal = real


def test_start_offers_only_a_github_origin():
    real = pr_review._repo_root
    with tempfile.TemporaryDirectory() as repo, tempfile.TemporaryDirectory() as data:
        subprocess.run(["git", "init", "-q", repo], check=True)
        pr_review._repo_root = lambda: Path(repo)
        for url, current in (("https://gitlab.com/acme/api.git", "none"), ("https://mygithub.com/acme/api.git", "none"),
                             ("git@github.com:acme/api.git", "acme/api"), ("https://github.com/acme/api/", "acme/api")):
            subprocess.run(["git", "-C", repo, "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "-C", repo, "remote", "add", "origin", url], check=True)
            lines = []
            pr_review.start(data, out=lines.append)
            assert lines == [f"CHOOSE current={current} before=none"], (url, lines)
    pr_review._repo_root = real


def test_failed_unwatch_cleanup_retries_on_next_tick():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        pr_review._write(pr_review.ledger_path(data, "o/r"), {"repo": "o/r", "prs": {"7": {**entry(), "worker": "ctx_7"}}})
        lines = []
        stub_orca(FakeOrca(cleanup_fail="rm failed"))
        pr_review.unwatch(data, "o/r", out=lines.append)
        assert lines[0].startswith("Cleanup failed for o/r#7") and lines[-1].startswith("Stopped watching o/r")
        assert pr_review.read_ledger(data, "o/r")["prs"]["7"]["worker"] == "ctx_7"
        fake = stub_orca(FakeOrca())
        pr_review.gh = fake_github({}, [])
        pr_review.tick(data, out=lines.append)
        assert fake.cleaned == cleanup_of("ctx_7")
        assert pr_review.read_ledger(data, "o/r")["prs"]["7"]["worker"] is None


def test_loop_end_stops_the_loop():
    real, pr_review._terminal = pr_review._terminal, lambda: None
    with tempfile.TemporaryDirectory() as data:
        lines = []
        pr_review.watch(data, "o/r", ["loopEndHours=2"], out=lines.append)
        pr_review.start(data, ["o/r"], out=lines.append)
        pr_review.set_cron(data, "job-1", out=lines.append)
        end = datetime.fromisoformat(json.loads(pr_review._loop_file(data).read_text())["loopEnd"])
        assert timedelta(hours=1, minutes=59) < end - datetime.now(timezone.utc) <= timedelta(hours=2)
        pr_review.gh = fake_github({}, [])
        stub_orca(FakeOrca())
        lines.clear()
        pr_review.tick(data, out=lines.append, now=end - timedelta(minutes=1))
        assert lines == [] and json.loads(pr_review._loop_file(data).read_text())["active"]
        pr_review.gh = lambda *a: (_ for _ in ()).throw(AssertionError("a tick past the Loop End scans nothing"))
        pr_review.tick(data, out=lines.append, now=end)
        assert lines[0] == "CRON job-1" and lines[1].startswith("The loop reached its Loop End at ")
        loop = json.loads(pr_review._loop_file(data).read_text())
        assert loop["active"] is False and loop["cron"] is None
        # A stopped loop stays quiet: a manual tick past the Loop End scans as usual.
        pr_review.gh = fake_github({}, [])
        lines.clear()
        pr_review.tick(data, out=lines.append, now=end + timedelta(hours=1))
        assert lines == []
    pr_review._terminal = real


def test_watch_saved_settings_confirm_and_new_keys():
    real = pr_review.repo_slug, pr_review._terminal
    pr_review.repo_slug, pr_review._terminal = lambda path, host="": "o/r", lambda: None
    with tempfile.TemporaryDirectory() as data:
        lines = []
        pr_review.start(data, out=lines.append)
        assert lines == ["CHOOSE current=o/r before=none"]
        lines.clear()
        pr_review.show(data, "o/r", out=lines.append)
        assert lines == ["NEW o/r"]
        lines.clear()
        pr_review.watch(data, "o/r", ["mandatorySkills=sec-review, a11y", "recommendedSkills=",
                                      "instructions=Check the migrations.", "loopEndHours=4", "cadenceMinutes=10"],
                        out=lines.append)
        assert lines == ["Watching o/r: manual mode, a scan every 10 min, Loop End after 4 hours.",
                         "- Mandatory skills: sec-review, a11y", "- Recommended skills: none",
                         "- Special instructions: Check the migrations."]
        saved = json.loads((Path(data) / pr_review.SETTINGS_FILE).read_text())["o/r"]
        assert saved == {"watched": True, "mandatorySkills": ["sec-review", "a11y"], "recommendedSkills": [],
                         "instructions": "Check the migrations.", "loopEndHours": 4.0, "cadenceMinutes": 10}
        # The confirm path: saved settings print under SAVED, so the skill asks Use these or Change.
        lines.clear()
        pr_review.show(data, "o/r", out=lines.append)
        assert lines[0] == "SAVED o/r" and lines[1:] == ["o/r: manual mode, a scan every 10 min, Loop End after 4 hours.",
                                                         "- Mandatory skills: sec-review, a11y", "- Recommended skills: none",
                                                         "- Special instructions: Check the migrations."]
        # The new keys reach the review brief.
        spec = pr_review.worker_spec("o/r", pr(1), {**entry(), "round": 1}, "d.json", "r.md",
                                     settings=pr_review.settings_for(data, "o/r"))
        assert "- Mandatory skills: sec-review, a11y\n- Recommended skills: none\n- Special instructions: Check the migrations." in spec
        for bad in (["loopEndHours=0"], ["loopEndHours=200"], ["mode=loud"], ["colour=red"], ["cadenceMinutes"]):
            try:
                pr_review.watch(data, "o/r", bad, out=lines.append)
                assert False, bad
            except pr_review.Fail:
                pass
        # Starting with o/s alone makes it the only Watched Repo; o/r keeps its settings.
        lines.clear()
        pr_review.start(data, ["o/s"], out=lines.append)
        assert pr_review.watched_repos(data) == ["o/s"]
        assert pr_review.settings_for(data, "o/r")["mandatorySkills"] == ["sec-review", "a11y"]
        lines.clear()
        pr_review.start(data, out=lines.append)
        assert lines == ["CHOOSE current=o/r before=o/s"]
        lines.clear()
        pr_review.unwatch(data, "o/s", out=lines.append)
        assert pr_review.watched_repos(data) == [] and lines[-1].startswith("Stopped watching o/s.")
        try:
            pr_review.unwatch(data, "o/s")
            assert False
        except pr_review.Fail:
            pass
    pr_review.repo_slug, pr_review._terminal = real


def test_gh_timeout_on_the_second_pr_posts_the_first_once():
    with tempfile.TemporaryDirectory() as data:
        (Path(data) / "review-settings.json").write_text(json.dumps({"o/r": {"watched": True, "mode": "auto"}}))
        prs, posted, lines = {1: pr(1), 2: pr(2)}, [], []
        fake = fake_github(prs, [1, 2], posted)
        stub_orca(FakeOrca())
        pr_review.gh = fake
        pr_review.tick(data, out=lines.append)
        write_draft(data, 1, DRAFT)
        write_draft(data, 2, DRAFT)

        def slow_on_2(*args):
            if args[:3] == ("pr", "view", "2"):
                raise pr_review.Fail("`gh pr view` timed out after 30s")
            return fake(*args)
        pr_review.gh = slow_on_2
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == ["Posted o/r#1: CHANGES_REQUESTED, 1 inline comments. https://github.com/o/r/pull/1",
                         "Skipped o/r#2 this tick: `gh pr view` timed out after 30s. The next tick retries."]
        # The next tick reads PR 1 as posted and PR 2 recovers: each posts exactly once.
        pr_review.gh = fake
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert [p for p, _ in posted] == ["repos/o/r/pulls/1/reviews", "repos/o/r/pulls/2/reviews"]


def test_moved_head_posts_nothing_and_starts_a_new_round():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data)
        prs[1]["headRefOid"] = "bbb"
        lines = []
        pr_review.approve(data, "o/r#1", out=lines.append)
        assert posted == [] and lines == ["Did not post o/r#1: its head moved to bbb after the review started. "
                                          "Round 2 reviews the new head."]
        assert orca.cleaned == cleanup_of("ctx_1")
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert (e["round"], e["worker"], e["draft"], e["headSha"], e["verdict"]) == (2, None, None, None, None)
        # The next tick reviews the new head from scratch in round 2.
        lines.clear(); due(data); pr_review.tick(data, out=lines.append)
        assert lines == ["Reviewing o/r#1: a review worker started in its own worktree."]
        assert "- Head commit to review: bbb" in orca.specs[1] and "- Round: 2\n" in orca.specs[1]
        assert pr_review.read_ledger(data, "o/r")["prs"]["1"]["headSha"] == "bbb"


def test_failed_start_is_never_relaunched():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        lines = []
        pr_review.gh = fake_github({1: pr(1)}, [1])
        receipt = {"ok": False, "error": {"code": "runtime_error", "message": "setup failed"},
                   "result": {"failedStage": "setup", "residualResources": [{"kind": "worktree", "id": "wt_1"}]}}
        orca = stub_orca(FakeOrca(fail=pr_review.Fail("`orca orchestration worker-start` exited 1: runtime_error: setup failed", receipt)))
        pr_review.tick(data, out=lines.append)
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert e["startFailed"] == {"error": "`orca orchestration worker-start` exited 1: runtime_error: setup failed",
                                    "failedStage": "setup", "residualResources": [{"kind": "worktree", "id": "wt_1"}]}
        assert e["worker"] is None and e["startRequest"] is None
        assert "Failed stage: setup. Residual resources: [{\"kind\": \"worktree\", \"id\": \"wt_1\"}]." in lines[-1]
        assert "never relaunched" in lines[-1]
        # Later ticks start nothing and stay quiet, even once Orca would accept the start.
        orca.fail = None
        lines.clear(); due(data); pr_review.tick(data, out=lines.append); due(data); pr_review.tick(data, out=lines.append)
        assert lines == [] and len(orca.requests) == 1 and orca.specs == []
        # A receipt with no recovery fields still blocks the relaunch.
        assert pr_review.start_receipt(None) == {"failedStage": None, "residualResources": None}


def test_cleanup_retry_releases_once():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        prs = {1: pr(1)}
        pr_review.gh = fake_github(prs, [1])
        orca = stub_orca(FakeOrca())
        pr_review.tick(data, out=[].append)
        orca.rm_fail = 1
        prs[1]["state"] = "MERGED"
        due(data); pr_review.tick(data, out=[].append)
        due(data); pr_review.tick(data, out=[].append)
        # FakeOrca keeps the dispatch running, so the retry stops it again but releases it only once.
        assert [c for c in orca.cleaned if c[1] == "worker-release"] == [("orchestration", "worker-release", "ctx_1")]
        assert orca.cleaned[-1] == ("worktree", "rm", "id:repo-1::/wt/ctx_1")
        assert "released" not in pr_review.read_ledger(data, "o/r")["prs"]["1"]


def test_failed_start_with_a_string_error_is_never_relaunched():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        pr_review.gh = fake_github({1: pr(1)}, [1])
        orca = stub_orca(FakeOrca(fail=pr_review.Fail("`orca orchestration worker-start` exited 1: boom",
                                                      {"ok": False, "error": "boom"})))
        pr_review.tick(data, out=[].append)
        e = pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert e["startFailed"]["failedStage"] is None and e["worker"] is None
        orca.fail = None
        due(data); pr_review.tick(data, out=[].append)
        assert len(orca.requests) == 1 and orca.specs == []


def test_missing_orca_binary_is_retried():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        lines = []
        pr_review.gh = fake_github({1: pr(1)}, [1])
        orca = stub_orca(FakeOrca(fail=pr_review.Fail("orca is not installed", not_run=True)))
        pr_review.tick(data, out=lines.append)
        assert "startFailed" not in pr_review.read_ledger(data, "o/r")["prs"]["1"]
        assert lines[-1].endswith("The next tick retries.")
        orca.fail = None
        due(data); pr_review.tick(data, out=lines.append)
        assert len(orca.specs) == 1


def test_approve_during_a_held_lock():
    with tempfile.TemporaryDirectory() as data:
        prs, posted, orca = held(data)
        real = pr_review.plugin_data_dir
        pr_review.plugin_data_dir = lambda: Path(data)
        other = pr_review._lock(data)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                assert pr_review.main(["pr_review.py", "approve", "o/r#1"]) == 1
                sys.stdin = io.StringIO("Fix it.")
                assert pr_review.main(["pr_review.py", "feedback", "o/r#1"]) == 1
                # A tick that finds the lock held exits quietly.
                assert pr_review.main(["pr_review.py", "tick"]) == 0
            assert buf.getvalue().splitlines() == ["FAIL: a tick, approve or feedback is running. Run the command again in a minute"] * 2
            assert posted == [] and orca.sent == []
            other.close()
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                assert pr_review.main(["pr_review.py", "approve", "o/r#1"]) == 0
            assert [p for p, _ in posted] == ["repos/o/r/pulls/1/reviews"]
        finally:
            other.close()
            sys.stdin = sys.__stdin__
            pr_review.plugin_data_dir = real


def test_fork_pr_runs_no_evidence():
    with tempfile.TemporaryDirectory() as data:
        (Path(data) / pr_review.SETTINGS_FILE).write_text(json.dumps({"o/r": {"watched": True, "evidenceCommand": "touch ran"}}))
        prs = {1: {**pr(1), "isCrossRepository": True}}
        pr_review.gh = fake_github(prs, [1])
        orca = stub_orca(FakeOrca())
        ran = []
        real, pr_review.evidence_record = pr_review.evidence_record, lambda *a: ran.append(a)
        try:
            pr_review.tick(data, out=lambda line: None)
        finally:
            pr_review.evidence_record = real
        assert ran == [] and "- Evidence Record: none: fork PR" in orca.specs[0]


def finished_ledger(data, finished_at, **extra):
    """o/r's ledger holding PR 1, merged at `finished_at`, with `extra` fields."""
    pr_review._write(pr_review.ledger_path(data, "o/r"), {"repo": "o/r", "prs": {"1": {
        "number": 1, "title": "PR 1", "url": "u", "round": 1, "verdict": "APPROVED", "worker": None, "draft": None,
        "finishedAt": finished_at.isoformat(timespec="seconds"), "state": "MERGED", **extra}}})


def test_finished_entry_is_never_approved():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        draft = write_draft(data, 1, DRAFT)
        finished_ledger(data, datetime.now(timezone.utc), verdict=None, draft=str(draft))
        for call in (lambda: pr_review._held(data, "o/r#1"), lambda: pr_review.approve(data, "o/r#1"),
                     lambda: pr_review.feedback(data, "o/r#1", "shorter")):
            try:
                call()
                assert False
            except pr_review.Fail as e:
                assert "no Review Draft waits for o/r#1" in str(e)


def test_finished_entry_drops_after_the_window():
    with tempfile.TemporaryDirectory() as data:
        watching(data)
        (Path(data) / "settings.json").write_text(json.dumps({"recentWindowHours": 2}))
        pr_review.gh = fake_github({}, [])
        now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        # Exactly at the window edge, the entry stays.
        finished_ledger(data, now - timedelta(hours=2))
        pr_review.tick(data, out=lambda line: None, now=now)
        assert "1" in pr_review.read_ledger(data, "o/r")["prs"]
        # One second past it, the tick drops it.
        pr_review.tick(data, out=lambda line: None, now=now + timedelta(seconds=1))
        assert pr_review.read_ledger(data, "o/r")["prs"] == {}
        # review-settings.json does not set the window: settings.json does, default 120 hours.
        (Path(data) / "settings.json").unlink()
        finished_ledger(data, now - timedelta(hours=120))
        pr_review.tick(data, out=lambda line: None, now=now)
        assert "1" in pr_review.read_ledger(data, "o/r")["prs"]


def test_cadence_must_step_evenly():
    for good in (1, 5, 15, 30, 60, 120, 360, 1440):
        assert pr_review.parse_setting("cadenceMinutes", str(good)) == good
    for bad in (0, -5, 7, 45, 90, 100, 300, 2880):
        try:
            pr_review.parse_setting("cadenceMinutes", str(bad))
            assert False, bad
        except pr_review.Fail as e:
            assert f"cadenceMinutes={bad} is not a valid Review Setting" in str(e)
    # Every cadence the check accepts gives a cron line that fires at an even step.
    for c in range(1, 1441):
        try:
            pr_review.parse_setting("cadenceMinutes", str(c))
        except pr_review.Fail:
            continue
        assert (c < 60 and 60 % c == 0) or (c % 60 == 0 and 24 % (c // 60) == 0), c


GH = pr_review.gh

if __name__ == "__main__":
    os.environ["CLAUDE_PLUGIN_DATA"] = tempfile.mkdtemp()
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
