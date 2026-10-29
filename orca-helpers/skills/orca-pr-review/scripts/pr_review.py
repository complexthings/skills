"""The orca-pr-review loop: list the PRs that want my review, classify each, claim the new ones.

Usage:
    python3 pr_review.py start            # print CHOOSE: the current repo and the repos watched before
    python3 pr_review.py start <owner/repo>...   # watch exactly these, register the loop, print the cron line
    python3 pr_review.py show <owner/repo>        # print SAVED and the repo's Review Settings, or NEW
    python3 pr_review.py watch <owner/repo> [key=value ...]   # save Review Settings and watch the repo
    python3 pr_review.py unwatch <owner/repo>     # stop watching; its settings stay saved
    python3 pr_review.py set-cron <id>    # record the session cron job id CronCreate returned
    python3 pr_review.py tick             # one scan: list, classify, claim, review, post
    python3 pr_review.py approve <owner/repo#n>   # post a Review Draft held in manual mode
    python3 pr_review.py feedback <owner/repo#n> < text   # send Review Feedback, read from stdin, on a held draft to its worker
    python3 pr_review.py stop             # mark the loop stopped, print the cron id to delete
    python3 pr_review.py status           # print the ledger

A tick lists open PRs in Watched Repos where review is requested from me or my
team, or that are assigned to me, plus every PR a Watched Repo's ledger tracks.
A PR in any other repo is never a candidate. Once the Loop End passes, the tick
stops the loop instead of scanning. It reads each with
`gh pr view` and classifies it with `classify()`:

    UNSUPPORTED  I authored it; I never review myself
    IDLE         merged or closed, or reviewed and nothing new since
    CLAIMED      someone else is assigned and I am not; skipped silently
    INFLIGHT     claimed by me, review not finished
    FOLLOWUP     I requested changes and the head moved since
    NEW          not in the ledger, and nobody else is assigned

A NEW PR is claimed: `claim()` assigns me only when nobody is assigned, re-reads
the assignees, and backs off when someone else got it too. A claimed PR then
moves through `advance()`, one step per tick:

    no worker            dispatch a review worker in its own Orca worktree, on the
                         Orchestration Worker Model Slot from Prompt Settings
    worker, no draft     wait for the worker to write the Review Draft JSON
    draft, no verdict    auto mode: post it. Manual mode: hold it until `approve`.

`feedback` sends the user's Review Feedback on a held draft to its review worker,
or to a fresh worker on the same worktree when the old one is gone. The worker
rewrites the draft, and the rewrite is held for `approve` even in auto mode.

A FOLLOWUP PR starts the next round: its brief carries only the diff from the
head I reviewed to the new head, plus the earlier round's findings. A worker
that settled or sat idle without writing its draft is stopped, cleaned up and
restarted, at most MAX_RESTARTS times a round. After posting, a drop, a merge or
a close, `cleanup()` stops the worker, releases it with `worker-release` and removes
its worktree; a failed cleanup prints once and retries on the next tick.

A worker-start that exits non-zero is never relaunched: the entry keeps its
`failedStage` and `residualResources` in `startFailed` and the tick prints them
once. A worker-start whose reply was lost (a timeout) is replayed on the next tick
with the same `--retry-request` id, so Orca joins the first start instead of
starting a second worker.

Before posting, `post()` re-reads the assignees and the head. It drops the draft
when someone else took the PR, and posts nothing but starts a new round when the
head moved since the worker started. A fork PR (`isCrossRepository`) never runs the
evidence command. A merged or closed PR stays in the ledger once its cleanup succeeds,
with `finishedAt` and its final `state`. Nothing reads a finished entry again: no `gh`
call, claim, post, `approve` or `feedback`. Each tick first drops a finished entry
whose `finishedAt` is more than `recentWindowHours` (settings.json, default 120) old.
A tick that changes nothing prints nothing, and a held draft or a dispatch error
prints once. Every `gh` and `orca` call runs under a timeout with stdin from
/dev/null. A failure on one PR prints once and the tick moves to the next PR,
saving the ledger after each. Any other failure prints one `FAIL:` line and exits 1.

`tick`, `approve` and `feedback` hold `pr-review/.lock` for their whole run. A tick
that finds it held exits quietly; `approve` and `feedback` fail and ask for a rerun.

Every verb prints the final text for the user. A line starting with CHOOSE,
SAVED, NEW, RUNNING, CRON or NO CRON is an instruction for the skill instead.

Files in the Plugin Data Dir (`${CLAUDE_PLUGIN_DATA}`, or ~/.claude/orca-helpers/):

    review-settings.json   Review Settings, keyed by "owner/repo":
                           {"owner/repo": {"watched": bool, "mode": "manual"|"auto", "gifs": bool,
                                           "cadenceMinutes": "int: divides 60, or whole hours dividing 24",
                                           "loopEndHours": number,
                                           "mandatorySkills": [str], "recommendedSkills": [str],
                                           "instructions": "string: special instructions for the reviewer",
                                           "evidenceCommand": "string, optional"}}
                           A missing repo or key reads as DEFAULTS. A Watched Repo has "watched": true.
    pr-review/loop.json    {"cron": "string | null: the session cron job id", "active": bool,
                            "cadenceMinutes": int, "startedAt": "ISO 8601 UTC",
                            "loopEnd": "ISO 8601 UTC: the tick stops the loop at this time",
                            "repoPath": "the repo `start` ran in",
                            "terminal": "string | null: the Orca terminal `start` ran in, the loop's session"}
    pr-review/gifs-used.json   the last 10 GIF URLs posted, oldest first. With "gifs" on,
                           `post()` ends the review body with one GIF from
                           references/gifs.json that is not among them and answers 200.
    pr-review/<owner>__<repo>.json   the per-repo ledger:
                           {"repo": "owner/repo", "scannedAt": "ISO 8601 UTC | null",
                            "evidenceReported": "bool: the UNSUPPORTED-evidence line was printed",
                            "prs": {"<number>": {"number": int, "title": str, "url": str, "author": str,
                                                 "claimedAt": "ISO 8601 UTC", "headSha": "string | null: head reviewed",
                                                 "round": int, "verdict": "APPROVED | CHANGES_REQUESTED | COMMENTED | null",
                                                 "worker": "string | null: review worker handle, null once cleaned up",
                                                 "since": "string | null: the head an earlier round reviewed; a round 2+ brief diffs from it",
                                                 "restarts": "int: stuck review workers restarted this round",
                                                 "harness": "string | null: review worker Agent Harness",
                                                 "draft": "string | null: Review Draft path, set once the worker wrote it",
                                                 "feedback": "string | null: the user's last Review Feedback this round; a set value holds the rewrite",
                                                 "note": "string | null: the last line printed for this PR",
                                                 "startRequest": "string | null: the --retry-request id of a worker-start whose reply was lost",
                                                 "released": "string | absent: the dispatch cleanup already released while its worktree rm retries",
                                                 "startFailed": "{error, failedStage, residualResources} | absent: a worker-start that exited non-zero; never relaunched",
                                                 "finishedAt": "ISO 8601 UTC, set once the PR merged or closed and its cleanup succeeded",
                                                 "state": "MERGED | CLOSED, set with finishedAt"}}}
    pr-review/reviews/<owner>__<repo>-<n>/round-<r>.json   the Review Draft the worker writes:
                           {"event": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
                            "body": "the review body, in the Communication Standard PR comment format",
                            "comments": [{"path": "file path", "line": int, "body": str}]}
    pr-review/reviews/<owner>__<repo>-<n>/round-<r>.md     the worker's report
    pr-review/reviews/<owner>__<repo>-<n>/round-<r>.before-feedback.json   the draft the user sent Review Feedback on

`start` also upserts the loop into the Run Registry (`runs.json`) as workstream
`orca-pr-review` with `"kind": "pr-review"`, keyed by the repo it was started from.
That repo's `.orca/prompts/prompt-settings.json` picks the review worker's model.
"""
import fcntl
import json
import os
import random
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULTS = {"watched": False, "mode": "manual", "gifs": False, "cadenceMinutes": 5, "loopEndHours": 8,
            "mandatorySkills": [], "recommendedSkills": [], "instructions": ""}
# The session cron expires after 7 days, so a later Loop End never comes.
MAX_LOOP_END_HOURS = 168
SETTINGS_FILE = "review-settings.json"
REGISTRY_FILE = "runs.json"
WORKSTREAM = "orca-pr-review"
GH_TIMEOUT = 30
# worker-start creates a worktree and may run its setup hook before it returns.
ORCA_TIMEOUT = 300
EVIDENCE_TIMEOUT = 1800
# A worker idle at its prompt this long with no Review Draft is stuck, not between turns.
STUCK_AFTER = timedelta(minutes=10)
MAX_RESTARTS = 2
SKILL_DIR = Path(__file__).parent.parent
WORKER_BRIEF = SKILL_DIR / "references" / "review-worker.md"
COMM_STANDARD = SKILL_DIR.parent.parent / "references" / "communication-standard.md"
GIFS_FILE = SKILL_DIR / "references" / "gifs.json"
RECENT_GIFS = 10
# Draft event -> the ledger verdict once posted, and the one-line body when the draft has none.
EVENTS = {"APPROVE": ("APPROVED", "Approved: 0 blocking findings."),
          "REQUEST_CHANGES": ("CHANGES_REQUESTED", "Changes requested."),
          "COMMENT": ("COMMENTED", "Comments: 0 blocking findings.")}

sys.path.insert(0, str(SKILL_DIR.parent / "orca-prompt" / "scripts"))
from orca_cli import orca_cli  # noqa: E402
from scaffold import launch_flags, orca_agent, repo_slug, write_text_atomic  # noqa: E402
sys.path.insert(0, str(SKILL_DIR.parent / "orca-board" / "scripts"))
from board import plugin_data_dir, recent_window_hours  # noqa: E402
VIEW_FIELDS = "number,title,url,state,author,assignees,headRefOid,baseRefName,headRefName,isCrossRepository"


class Fail(Exception):
    """`receipt` is the failed command's --json output, when it printed one; `timed_out` marks a lost reply;
    `not_run` marks a command that never ran."""
    def __init__(self, message, receipt=None, timed_out=False, not_run=False):
        super().__init__(message)
        self.receipt, self.timed_out, self.not_run = receipt, timed_out, not_run


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(data, indent=2) + "\n", ".pr-review-")


def _run(tool, args, timeout):
    """Run `tool` (a command word, or an argv prefix such as orca_cli()) under a timeout and return its stdout; raise Fail on a timeout or non-zero exit."""
    argv = [tool] if isinstance(tool, str) else list(tool)
    tool = shlex.join(argv)
    try:
        r = subprocess.run([*argv, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Fail(f"`{tool} {args[0]} {args[1]}` timed out after {timeout}s", timed_out=True)
    except FileNotFoundError:
        raise Fail(f"{tool} is not installed", not_run=True)
    if r.returncode:
        try:
            receipt = json.loads(r.stdout)
        except ValueError:
            receipt = None
        try:
            # orca --json prints its error as JSON, so the last stderr line alone is a bare `}`.
            err = receipt["error"]
            last = f"{err['code']}: {err['message']}"
        except (KeyError, TypeError):
            last = (r.stderr.strip().splitlines() or [""])[-1]
        raise Fail(f"`{tool} {args[0]} {args[1]}` exited {r.returncode}: {last}", receipt)
    return r.stdout


def gh(*args):
    return _run("gh", args, GH_TIMEOUT)


def orca(*args):
    return _run(orca_cli(), args, ORCA_TIMEOUT)


# --- Review Settings -------------------------------------------------------

def _all_settings(data_dir):
    data = _read(Path(data_dir) / SETTINGS_FILE, {})
    return {r: e for r, e in data.items() if isinstance(e, dict)} if isinstance(data, dict) else {}


def repo_key(data_dir, repo):
    """The key `repo` has in Review Settings and the ledger: the saved spelling that matches it
    without case, else `repo` as given. GitHub, git remotes and users spell owner/repo in any case."""
    saved = _all_settings(data_dir)
    if repo in saved:
        return repo
    return next((r for r in saved if r.lower() == repo.lower()), repo)


def settings_for(data_dir, repo):
    """The Review Settings for `repo`, every missing key filled from DEFAULTS."""
    return {**DEFAULTS, **_all_settings(data_dir).get(repo_key(data_dir, repo), {})}


def watched_repos(data_dir):
    """The Watched Repos: every repo whose Review Settings set "watched": true."""
    return sorted(r for r, e in _all_settings(data_dir).items() if e.get("watched"))


def loop_cadence(data_dir):
    """The cron cadence: the shortest cadenceMinutes any Watched Repo sets, else the default."""
    return min([int(settings_for(data_dir, r)["cadenceMinutes"]) for r in watched_repos(data_dir)]
               or [DEFAULTS["cadenceMinutes"]])


def _check_repo(repo):
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise Fail(f"{repo} is not owner/repo")
    return repo


def parse_setting(key, value):
    """One `key=value` argument as its Review Settings value; raise Fail when it does not fit."""
    if key in ("mandatorySkills", "recommendedSkills"):
        return [v.strip() for v in value.split(",") if v.strip()]
    if key in ("instructions", "evidenceCommand"):
        return value.strip()
    if key == "mode" and value in ("manual", "auto"):
        return value
    if key == "gifs" and value in ("true", "false"):
        return value == "true"
    try:
        # The cron line steps minutes within an hour, or whole hours within a day: any other step drifts.
        if key == "cadenceMinutes" and int(value) >= 1 and (60 % int(value) == 0 if int(value) < 60
                                                            else int(value) % 60 == 0 and 1440 % int(value) == 0):
            return int(value)
        if key == "loopEndHours" and 0 < float(value) <= MAX_LOOP_END_HOURS:
            return float(value)
    except ValueError:
        pass
    raise Fail(f"{key}={value} is not a valid Review Setting. Keys: mode=manual|auto, gifs=true|false, "
               f"cadenceMinutes=<a divisor of 60, or hours dividing 24 such as 120>, loopEndHours=<1-{MAX_LOOP_END_HOURS}>, mandatorySkills=<a,b>, "
               "recommendedSkills=<a,b>, instructions=<text>, evidenceCommand=<command>")


def save_settings(data_dir, changes):
    """Merge {repo: {key: value}} into review-settings.json."""
    path = Path(data_dir) / SETTINGS_FILE
    data = _read(path, None) if path.exists() else {}
    # An unreadable file holds settings the user wrote by hand: overwriting it loses them.
    if not isinstance(data, dict):
        raise Fail(f"{path} is not a JSON object. Fix or delete it, then run the command again")
    for repo, values in changes.items():
        repo = repo_key(data_dir, repo)
        data[repo] = {**(data.get(repo) if isinstance(data.get(repo), dict) else {}), **values}
    _write(path, data)


def describe(repo, s):
    """The user-facing lines for `repo`'s Review Settings `s`."""
    return [f"{repo}: {s['mode']} mode, a scan every {s['cadenceMinutes']} min, Loop End after {s['loopEndHours']:g} hours.",
            f"- Mandatory skills: {', '.join(s['mandatorySkills']) or 'none'}",
            f"- Recommended skills: {', '.join(s['recommendedSkills']) or 'none'}",
            f"- Special instructions: {s['instructions'] or 'none'}"]


def show(data_dir, repo, out=print):
    """SAVED and the saved Review Settings for `repo`, or NEW when it has none."""
    repo = repo_key(data_dir, _check_repo(repo))
    if repo not in _all_settings(data_dir):
        out(f"NEW {repo}")
        return
    out(f"SAVED {repo}")
    for line in describe(repo, settings_for(data_dir, repo)):
        out(line)


def watch(data_dir, repo, pairs, out=print):
    """Save `pairs` (key=value) as `repo`'s Review Settings and make it a Watched Repo."""
    repo = repo_key(data_dir, _check_repo(repo))
    values = {"watched": True}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise Fail(f"{pair} is not key=value")
        values[key] = parse_setting(key, value)
    save_settings(data_dir, {repo: values})
    lines = describe(repo, settings_for(data_dir, repo))
    for line in [f"Watching {lines[0]}", *lines[1:]]:
        out(line)


def unwatch(data_dir, repo, out=print):
    """Stop watching `repo`: keep its settings and ledger, clean up its review workers."""
    repo = repo_key(data_dir, _check_repo(repo))
    if repo not in watched_repos(data_dir):
        raise Fail(f"{repo} is not a Watched Repo. Watched Repos: {', '.join(watched_repos(data_dir)) or 'none'}")
    save_settings(data_dir, {repo: {"watched": False}})
    led = read_ledger(data_dir, repo)
    for number, entry in led["prs"].items():
        if entry.get("worker"):
            _clean(repo, number, entry, out)
    _write(ledger_path(data_dir, repo), led)
    out(f"Stopped watching {repo}. Its Review Settings stay saved. **/orca-pr-review watch {repo}** resumes it.")


# --- Ledger ----------------------------------------------------------------

def ledger_path(data_dir, repo):
    return Path(data_dir) / "pr-review" / (repo_key(data_dir, repo).replace("/", "__") + ".json")


def read_ledger(data_dir, repo):
    repo = repo_key(data_dir, repo)
    led = _read(ledger_path(data_dir, repo), {})
    return {"repo": repo, "scannedAt": led.get("scannedAt"), "evidenceReported": led.get("evidenceReported", False),
            "prs": led.get("prs") or {}}


def all_ledgers(data_dir):
    d = Path(data_dir) / "pr-review"
    return [read_ledger(data_dir, _read(p, {}).get("repo")) for p in sorted(d.glob("*__*.json"))
            if _read(p, {}).get("repo")]


# --- Classifier ------------------------------------------------------------

def _logins(pr):
    return {a["login"] for a in pr.get("assignees") or []}


def classify(pr, me, entry):
    """One action for `pr` (gh pr view JSON), given my login and its ledger entry or None."""
    if (pr.get("author") or {}).get("login") == me:
        return "UNSUPPORTED"
    if pr.get("state") != "OPEN":
        return "IDLE"
    assignees = _logins(pr)
    if assignees and me not in assignees:
        return "CLAIMED"
    if entry is None:
        return "NEW"
    if entry.get("verdict") is None:
        return "INFLIGHT"
    if entry["verdict"] == "CHANGES_REQUESTED" and pr.get("headRefOid") != entry.get("headSha"):
        return "FOLLOWUP"
    return "IDLE"


# --- Claim -----------------------------------------------------------------

def claim(repo, number, me, run=None):
    """Assign me when nobody is assigned, re-read, back off on a race. True when the PR is mine."""
    run = run or gh
    view = lambda: _logins(json.loads(run("pr", "view", str(number), "-R", repo, "--json", "assignees")))
    before = view()
    if before:
        return before == {me}
    run("pr", "edit", str(number), "-R", repo, "--add-assignee", me)
    after = view()
    # Two reviewers can both see an empty list: the lowest login keeps it, so exactly one backs off.
    if me in after and min(after) == me:
        return True
    if me in after:
        run("pr", "edit", str(number), "-R", repo, "--remove-assignee", me)
    return False


# --- Review worker, Review Draft and posting --------------------------------

def review_paths(data_dir, repo, number, rnd):
    """(draft, report) for round `rnd` of `repo#number`."""
    d = Path(data_dir) / "pr-review" / "reviews" / f"{repo.replace('/', '__')}-{number}"
    return d / f"round-{rnd}.json", d / f"round-{rnd}.md"


def worker_harness(repo_path):
    """The Agent Harness the review worker runs on: Prompt Settings' Main Orchestrator harness,
    else its first, else Claude Code with its own default model."""
    settings = _read(Path(repo_path) / ".orca" / "prompts" / "prompt-settings.json", {})
    harnesses = [h for h in settings.get("harnesses") or [] if isinstance(h, dict) and h.get("name")]
    main = next((h for h in harnesses if h["name"] == settings.get("mainOrchestratorHarness")), None)
    return main or (harnesses[0] if harnesses else {"name": "claude"})


def orca_repo(repo):
    """The Orca repo ({id, path, ...}) whose origin, on any host, ends in <repo>."""
    for r in (json.loads(orca("repo", "list", "--json")).get("result") or {}).get("repos") or []:
        if "path" in r and (repo_slug(r["path"]) or "").lower() == repo.lower():
            return r
    raise Fail(f"no Orca repo has the origin github.com/{repo}. Add its clone to Orca")


def _worker_handle(out):
    """The dispatch or terminal id in `worker-start --json` output, else None."""
    res = json.loads(out).get("result") or {}
    for d in (res, *(v for v in res.values() if isinstance(v, dict))):
        for key in ("dispatchId", "terminal", "handle", "id"):
            if isinstance(d.get(key), str):
                return d[key]
    return None


def evidence_record(clone, number, sha, command):
    """Run `command` once in a detached checkout of `sha`, PR `number`'s head; the Evidence Record."""
    git = lambda *a: _run("git", ["-C", str(clone), *a], GH_TIMEOUT)
    with tempfile.TemporaryDirectory(prefix="pr-review-evidence-") as tmp:
        tree = Path(tmp) / "head"
        git("fetch", "origin", f"pull/{number}/head")
        git("worktree", "add", "--detach", str(tree), sha)
        try:
            r = subprocess.run(command, shell=True, cwd=tree, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=EVIDENCE_TIMEOUT)
            code, output = r.returncode, r.stdout
        except subprocess.TimeoutExpired as e:
            code, output = f"timeout after {EVIDENCE_TIMEOUT}s", e.stdout or ""
            output = output.decode(errors="replace") if isinstance(output, bytes) else output
        finally:
            git("worktree", "remove", "--force", str(tree))
    # A non-zero exit is evidence for the reviewer, not a reason to stop.
    return f"Evidence Record, commit {sha}, exit {code}\n{output}"


def worker_spec(repo, pr, entry, draft, report, evidence=None, followup=None, settings=None):
    """The review worker's dispatch spec: the brief, then this review's facts.
    `followup` is (diff, earlier findings) for round 2 and later; `settings` the repo's Review Settings."""
    s = settings or DEFAULTS
    record = (f"commit {pr['headRefOid']}, in the section below" if evidence
              else "none: fork PR" if pr.get("isCrossRepository") else "none: no evidence command is set")
    section = f"\n## Evidence Record\n\n````text\n{evidence.rstrip()}\n````\n" if evidence else ""
    if followup:
        diff, findings = followup
        section += (f"\n## Changes since round {entry['round'] - 1}\n\nThe diff from {entry['since']}, the head round "
                    f"{entry['round'] - 1} reviewed, to {pr['headRefOid']}. Review only this diff.\n\n"
                    f"````diff\n{diff.rstrip()}\n````\n\n## Earlier findings\n\n{findings.rstrip()}\n")
    if entry.get("feedback"):
        section += feedback_section(entry, draft)
    return WORKER_BRIEF.read_text() + f"""
## This review

- PR: {repo}#{pr['number']}, {pr['title']}. {pr['url']}
- Author: {pr['author']['login']}
- Base branch: {pr['baseRefName']}
- Head commit to review: {pr['headRefOid']}
- Round: {entry['round']}{f", a follow-up: review only the changes since {entry['since']}" if followup else ""}
- Evidence Record: {record}
- Report path: {report}
- Draft path: {draft}
- Communication Standard: {COMM_STANDARD}
- Mandatory skills: {', '.join(s['mandatorySkills']) or 'none'}
- Recommended skills: {', '.join(s['recommendedSkills']) or 'none'}
- Special instructions: {s['instructions'] or 'none'}
""" + section


def _before_feedback(draft):
    """Where the draft the user sent Review Feedback on is kept: round-<r>.before-feedback.json."""
    return Path(draft).with_suffix(".before-feedback.json")


def feedback_section(entry, draft):
    """The Review Feedback section: the user's feedback and the draft it answers."""
    before = json.dumps(_read(_before_feedback(draft), None), indent=2)
    return (f"\n## Review Feedback\n\nThe user read your Review Draft and asks for changes before it posts:\n\n"
            f"{entry['feedback'].strip()}\n\nThe draft they read:\n\n````json\n{before}\n````\n\n"
            f"Rewrite the report at {Path(draft).with_suffix('.md')} and the Review Draft at {draft} to answer it, "
            "then send `worker_done`.\n")


def followup_brief(data_dir, repo, pr, entry):
    """(diff, earlier findings) for a round 2+ review: only the commits since the head I reviewed."""
    diff = gh("api", "-H", "Accept: application/vnd.github.diff",
              f"repos/{repo}/compare/{entry['since']}...{pr['headRefOid']}")
    draft, report = review_paths(data_dir, repo, pr["number"], entry["round"] - 1)
    findings = report.read_text() if report.exists() else _read(draft, {}).get("body") or ""
    return diff, findings or "None recorded: the earlier report is missing."


def _tree_name(repo, number):
    return f"review-{repo.split('/')[-1]}-{number}"


def dispatch(data_dir, repo, pr, entry, tree=None):
    """Start the review worker for `entry` in a new Orca worktree, or in the worktree selector `tree`; return its handle."""
    harness = worker_harness(_read(_loop_file(data_dir), {}).get("repoPath") or _repo_root())
    draft, report = review_paths(data_dir, repo, pr["number"], entry["round"])
    clone = orca_repo(repo)
    followup = followup_brief(data_dir, repo, pr, entry) if entry.get("since") else None
    settings = settings_for(data_dir, repo)
    command = settings.get("evidenceCommand")
    # A fork PR's head is code nobody vetted: never run it on this machine.
    run = command and not pr.get("isCrossRepository")
    evidence = evidence_record(clone["path"], pr["number"], pr["headRefOid"], command) if run else None
    # One id per start: a replay after a lost reply joins the first start instead of starting a second worker.
    entry["startRequest"] = entry.get("startRequest") or f"pr-review-{uuid.uuid4().hex}"
    try:
        out = orca(
            "orchestration", "worker-start",
            "--spec", worker_spec(repo, pr, entry, draft, report, evidence, followup, settings),
            # Orca rejects creation flags for an existing worktree.
            *(("--worktree", tree) if tree else
              ("--worktree", "new-top-level", "--repo", f"id:{clone['id']}", "--base-branch", pr["baseRefName"],
               "--name", _tree_name(repo, pr["number"]))),
            "--task-title", f"Review {repo}#{pr['number']}",
            "--agent", orca_agent(harness), *shlex.split(launch_flags(harness)),
            "--retry-request", entry["startRequest"], "--json",
        )
    except Fail as e:
        # A missing binary started nothing, so the next tick may start it.
        if not e.timed_out and not e.not_run:
            entry["startRequest"] = None
            entry["startFailed"] = {"error": str(e), **start_receipt(e.receipt)}
        raise
    entry["startRequest"] = None
    entry["harness"] = harness["name"]
    return _worker_handle(out) or "started"


def start_receipt(receipt):
    """`failedStage` and `residualResources` from a failed worker-start's --json receipt, None when absent."""
    receipt = receipt if isinstance(receipt, dict) else {}
    err = receipt.get("error")
    for d in (receipt.get("result"), err.get("data") if isinstance(err, dict) else None, receipt):
        if isinstance(d, dict) and ("failedStage" in d or "residualResources" in d):
            return {"failedStage": d.get("failedStage"), "residualResources": d.get("residualResources")}
    return {"failedStage": None, "residualResources": None}


def draft_problem(draft):
    """Why `draft` is not a postable Review Draft, or None."""
    if not isinstance(draft, dict) or draft.get("event") not in EVENTS:
        return f"event must be one of {', '.join(EVENTS)}"
    if not isinstance(draft.get("body", ""), str):
        return "body must be a string"
    comments = draft.get("comments", [])
    ok = lambda c: (isinstance(c, dict) and isinstance(c.get("path"), str) and isinstance(c.get("body"), str)
                    and isinstance(c.get("line"), int) and c["line"] > 0)
    if not isinstance(comments, list) or not all(map(ok, comments)):
        return "comments must be a list of {path, line, body}"
    return None


def review_payload(draft, sha):
    """The `POST /pulls/<n>/reviews` body for `draft`, reviewed at commit `sha`."""
    comments = [{"path": c["path"], "line": c["line"], "side": "RIGHT", "body": c["body"]}
                for c in draft.get("comments", [])]
    body = draft.get("body", "").strip()
    # GitHub rejects REQUEST_CHANGES or COMMENT with no body and no inline comments.
    if not body and not comments and draft["event"] != "APPROVE":
        body = EVENTS[draft["event"]][1]
    return {"commit_id": sha, "event": draft["event"], "body": body, "comments": comments}


def gif_ok(url):
    """True when `url` answers a HEAD request with 200."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=10) as r:
            return r.status == 200
    except (OSError, ValueError):
        return False


def pick_gif(data_dir, ok=None):
    """A random GIF ({url, alt}) from the shipped list that is not one of the last 10 used
    and returns 200, recorded as used; None when no GIF qualifies."""
    ok = ok or gif_ok
    used_file = Path(data_dir) / "pr-review" / "gifs-used.json"
    used = _read(used_file, [])
    fresh = [g for g in json.loads(GIFS_FILE.read_text()) if g["url"] not in used[-RECENT_GIFS:]]
    for gif in random.sample(fresh, len(fresh)):
        if ok(gif["url"]):
            _write(used_file, (used + [gif["url"]])[-RECENT_GIFS:])
            return gif
    return None


def _say(entry, line, out):
    """Print `line` once: a held draft or a repeated error stays quiet on later ticks."""
    if entry.get("note") != line:
        entry["note"] = line
        out(line)


def _worker_show(handle):
    return json.loads(orca("orchestration", "worker-show", "--dispatch", handle, "--json")).get("result") or {}


def cleanup(entry):
    """Stop `entry`'s review worker, release it and remove its worktree.
    Raises Fail and keeps `entry["worker"]` when a step fails, so the next tick retries."""
    handle = entry.get("worker")
    # "started" means worker-start named no handle, so there is nothing to find again.
    if handle and handle != "started":
        show = _worker_show(handle)
        if (show.get("dispatch") or {}).get("status") not in ("completed", "failed", "stopped"):
            orca("orchestration", "worker-stop", "--dispatch", handle, "--json")
        # Release closes only the worker's own terminal; `terminal close --all` would take setup terminals too.
        # A retry after a failed `worktree rm` does not release the dispatch a second time.
        if entry.get("released") != handle:
            orca("orchestration", "worker-release", "--dispatch", handle, "--json")
            entry["released"] = handle
        tree = (show.get("worker") or {}).get("worktreeId")
        if tree:
            orca("worktree", "rm", "--worktree", f"id:{tree}", "--force", "--json")
    entry["worker"] = None
    entry.pop("released", None)


def _clean(repo, number, entry, out):
    """cleanup(), printing a failure once. True when nothing is left behind."""
    try:
        cleanup(entry)
        return True
    except Fail as e:
        _say(entry, f"Cleanup failed for {repo}#{number}: {e}. The next tick retries.", out)
        return False


def liveness(dispatch):
    """The `projection.liveness` verdict on `dispatch`'s `worker-list --run` row, the authority on agent liveness; None when no row has it."""
    args = ("orchestration", "worker-list", "--run", dispatch.get("runId"), "--json")
    cursor = ()
    while True:
        res = json.loads(orca(*args[:-1], *cursor, args[-1])).get("result") or {}
        for row in res.get("workers") or []:
            if row.get("dispatchId") == dispatch.get("id"):
                return ((row.get("projection") or {}).get("liveness") or {}).get("verdict")
        page = res.get("page") or {}
        if not page.get("hasMore") or not page.get("nextCursor"):
            return None
        cursor = ("--cursor", page["nextCursor"])


def stuck(handle, now=None):
    """Why review worker `handle` stopped without a Review Draft, or None while it may still be working.
    Only positive evidence counts: a settled dispatch, an exited agent, or an idle prompt past STUCK_AFTER."""
    show = _worker_show(handle)
    dispatch = show.get("dispatch") or {}
    if dispatch.get("status") in ("completed", "failed", "stopped"):
        return f"its dispatch is {dispatch['status']} with no Review Draft"
    if dispatch.get("runId") and liveness(dispatch) == "exited":
        return "its agent exited"
    proj, term = show.get("projection") or {}, show.get("terminal") or {}
    # A prompt only a human can answer is a healthy wait, not a stall.
    if (show.get("observation") or {}).get("agentWait") or (proj.get("stage") or {}).get("activity") != "idle":
        return None
    quiet = (now or datetime.now(timezone.utc)) - datetime.fromtimestamp(term.get("lastOutputAt", 0) / 1000, timezone.utc)
    return f"it sat idle at its prompt for {int(quiet.total_seconds() // 60)} minutes" if quiet >= STUCK_AFTER else None


def drop(data_dir, led, number, taken, out=print):
    """Forget `number` and delete its draft: `taken` (other logins) now own the PR."""
    _clean(led["repo"], number, led["prs"][str(number)], out)
    entry = led["prs"].pop(str(number))
    review_paths(data_dir, led["repo"], number, entry["round"])[0].unlink(missing_ok=True)
    out(f"Dropped the Review Draft for {led['repo']}#{number}: {', '.join(sorted(taken))} took the PR.")


def post(data_dir, led, number, me, out=print):
    """Post `led`'s Review Draft for `number`, drop it when someone else took the PR,
    or start a new round when the head moved since the worker started."""
    repo, entry = led["repo"], led["prs"][str(number)]
    view = json.loads(gh("pr", "view", str(number), "-R", repo, "--json", "assignees,headRefOid"))
    taken = _logins(view)
    if taken and me not in taken:
        drop(data_dir, led, number, taken, out)
        return
    if view.get("headRefOid") != entry["headSha"]:
        if _clean(repo, number, entry, out):
            # `since` stays: it is the head the last posted round reviewed, so the next diff starts there.
            entry.update(round=entry["round"] + 1, headSha=None, draft=None, restarts=0, note=None, feedback=None)
            out(f"Did not post {repo}#{number}: its head moved to {str(view.get('headRefOid'))[:7]} after the review "
                f"started. Round {entry['round']} reviews the new head.")
        return
    draft = _read(entry["draft"], None)
    payload = review_payload(draft, entry["headSha"])
    gif = pick_gif(data_dir) if settings_for(data_dir, repo)["gifs"] else None
    if gif:
        payload["body"] = f"{payload['body']}\n\n![{gif['alt']}]({gif['url']})".strip()
    fd, tmp = tempfile.mkstemp(prefix=".pr-review-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f)
        gh("api", "-X", "POST", f"repos/{repo}/pulls/{number}/reviews", "--input", tmp)
    finally:
        os.unlink(tmp)
    entry["verdict"], entry["note"] = EVENTS[draft["event"]][0], None
    out(f"Posted {repo}#{number}: {entry['verdict']}, {len(payload['comments'])} inline comments. {entry['url']}")
    _clean(repo, number, entry, out)


def advance(data_dir, led, pr, me, out=print):
    """Move one claimed, unposted PR one step: dispatch, pick up its draft, then post or hold it."""
    repo, number, entry = led["repo"], pr["number"], led["prs"][str(pr["number"])]
    if entry["worker"] is None:
        entry["round"], entry["headSha"] = entry["round"] or 1, pr["headRefOid"]
        if not settings_for(data_dir, repo).get("evidenceCommand") and not led["evidenceReported"]:
            led["evidenceReported"] = True
            out(f"UNSUPPORTED-evidence {repo}: its Review Settings set no evidenceCommand, so each review brief "
                f"says Evidence Record: none. Add evidenceCommand to {repo} in review-settings.json to run one.")
        failed = entry.get("startFailed")
        if failed:
            _say(entry, f"No review worker for {repo}#{number}: {failed['error']}. Failed stage: "
                        f"{failed['failedStage'] or 'not reported'}. Residual resources: "
                        f"{json.dumps(failed['residualResources'])}. A failed start is never relaunched: clean up "
                        f"what remains, then delete prs.{number} from {ledger_path(data_dir, repo)} to review it again.", out)
            return
        try:
            entry["worker"] = dispatch(data_dir, repo, pr, entry)
        except Fail as e:
            if entry.get("startFailed"):
                return advance(data_dir, led, pr, me, out)
            _say(entry, f"No review worker for {repo}#{number}: {e}. The next tick retries.", out)
            return
        entry["note"] = None
        out(f"Reviewing {repo}#{number}: a review worker started in its own worktree.")
        return
    if entry["draft"] is None:
        draft_file, _ = review_paths(data_dir, repo, number, entry["round"])
        if not draft_file.exists():
            restart_if_stuck(data_dir, led, pr, me, out)
            return
        problem = draft_problem(_read(draft_file, None))
        if problem:
            _say(entry, f"The Review Draft for {repo}#{number} is not postable: {problem}. Fix {draft_file}.", out)
            return
        entry["draft"] = str(draft_file)
    # A draft rewritten from Review Feedback waits for the user even in auto mode.
    if settings_for(data_dir, repo)["mode"] == "auto" and not entry.get("feedback"):
        post(data_dir, led, number, me, out)
        return
    _, report = review_paths(data_dir, repo, number, entry["round"])
    event = _read(entry["draft"], {}).get("event")
    _say(entry, f"Review Draft ready for {repo}#{number}: {event}. Report: {report}. "
                f"Post it with **/orca-pr-review approve {repo}#{number}**.", out)


def restart_if_stuck(data_dir, led, pr, me, out=print):
    """Stop, clean up and re-dispatch a review worker that stopped without writing its draft."""
    repo, number, entry = led["repo"], pr["number"], led["prs"][str(pr["number"])]
    if entry["worker"] == "started":
        return
    try:
        why = stuck(entry["worker"])
    except Fail as e:
        _say(entry, f"Cannot check the review worker for {repo}#{number}: {e}. The next tick retries.", out)
        return
    if not why:
        return
    if entry.get("restarts", 0) >= MAX_RESTARTS:
        _say(entry, f"The review worker for {repo}#{number} is stuck again: {why}. It was restarted {MAX_RESTARTS} "
                    f"times this round. Read it with `orca orchestration worker-read --dispatch {entry['worker']}`.", out)
        return
    if not _clean(repo, number, entry, out):
        return
    entry["restarts"] = entry.get("restarts", 0) + 1
    out(f"Restarted the review worker for {repo}#{number}: {why}.")
    advance(data_dir, led, pr, me, out)


def start_round(led, pr, out=print):
    """Open the next round of a FOLLOWUP PR: review only the commits since the head I reviewed."""
    repo, number, entry = led["repo"], pr["number"], led["prs"][str(pr["number"])]
    if entry["worker"] and not _clean(repo, number, entry, out):
        return False
    entry.update(since=entry["headSha"], round=entry["round"] + 1, headSha=None, verdict=None, draft=None,
                 restarts=0, note=None, feedback=None)
    out(f"Round {entry['round']} for {repo}#{number}: new commits since my REQUEST_CHANGES at {entry['since'][:7]}.")
    return True


def _held(data_dir, target):
    """(ledger, entry) for the PR `owner/repo#n` whose Review Draft waits unposted; raise Fail when none does."""
    repo, _, number = target.partition("#")
    led = read_ledger(data_dir, repo)
    entry = led["prs"].get(number)
    if not number.isdigit() or not entry or not entry.get("draft") or entry.get("verdict") or entry.get("finishedAt"):
        raise Fail(f"no Review Draft waits for {target}. Run `pr_review.py status` to list the ledger")
    return led, entry


def approve(data_dir, target, out=print):
    """Post the Review Draft held for `owner/repo#n`."""
    led, entry = _held(data_dir, target)
    post(data_dir, led, entry["number"], gh("api", "user", "--jq", ".login").strip(), out)
    _write(ledger_path(data_dir, led["repo"]), led)


def feedback(data_dir, target, text, out=print):
    """Send Review Feedback on the draft held for `owner/repo#n` to its review worker, or to a fresh
    worker on the same worktree when the old one is gone. The rewritten draft is held again."""
    led, entry = _held(data_dir, target)
    repo, number, text = led["repo"], entry["number"], text.strip()
    if not text:
        raise Fail("the Review Feedback is empty. Say what the Review Draft should change")
    draft, handle = Path(entry["draft"]), entry.get("worker")
    # The worker rewrites the same path: moving the old draft aside makes the tick wait for the new one.
    try:
        os.replace(draft, _before_feedback(draft))
    except OSError as e:
        raise Fail(f"cannot move the Review Draft for {repo}#{number} aside: {e}")
    entry.update(draft=None, feedback=text, restarts=0, note=None)
    try:
        show, tree = {}, None
        if not handle or handle == "started":
            why = "Orca gave the old one no handle to reach it by"
        else:
            try:
                why = stuck(handle)
                if why:
                    show = _worker_show(handle)
                    why, tree = f"the old one {why}", (show.get("worker") or {}).get("worktreeId")
                    tree = tree and f"id:{tree}"
            except Fail as e:
                if "dispatch_not_found" not in str(e):
                    raise
                # Orca forgot the dispatch and with it the worktree id, so the worktree's name finds it.
                why, tree = "Orca no longer knows the old one", f"name:{_tree_name(repo, number)}"
        if not why:
            orca("orchestration", "send", "--to", f"dispatch:{handle}", "--subject", f"Review Feedback for {repo}#{number}",
                 "--body", feedback_section(entry, draft), "--json")
            said = f"Sent your Review Feedback to the review worker for {repo}#{number}."
        else:
            if (show.get("dispatch") or {}).get("status") not in (None, "completed", "failed", "stopped"):
                orca("orchestration", "worker-stop", "--dispatch", handle, "--json")
            pr = json.loads(gh("pr", "view", str(number), "-R", repo, "--json", VIEW_FIELDS))
            # The rewrite reviews the commit the draft reviewed, not a head pushed since.
            pr["headRefOid"] = entry["headSha"]
            entry["worker"] = dispatch(data_dir, repo, pr, entry, tree)
            said = f"Started a fresh review worker for {repo}#{number} with your Review Feedback: {why}."
    except Exception:
        os.replace(_before_feedback(draft), draft)
        raise
    _write(ledger_path(data_dir, repo), led)
    out(f"{said} The next tick holds its rewritten Review Draft for **/orca-pr-review approve {repo}#{number}**.")


# --- Tick ------------------------------------------------------------------

def candidates(data_dir):
    """(repo, number) for every open PR in a Watched Repo addressed to me, plus every PR its ledger tracks."""
    watched = watched_repos(data_dir)
    if not watched:
        return []
    repos = [a for r in watched for a in ("--repo", r)]
    found = set()
    for flag in ("--review-requested=@me", "--assignee=@me"):
        out = gh("search", "prs", flag, *repos, "--state=open", "--json", "repository,number", "--limit", "100")
        found |= {(p["repository"]["nameWithOwner"], p["number"]) for p in json.loads(out)}
    finished = set()
    for led in all_ledgers(data_dir):
        found |= {(led["repo"], int(n)) for n, e in led["prs"].items() if not e.get("finishedAt")}
        finished |= {(led["repo"], int(n)) for n, e in led["prs"].items() if e.get("finishedAt")}
    # GitHub answers in its own case: use the key the settings and ledger use.
    return sorted({(k, n) for k, n in ((repo_key(data_dir, r), n) for r, n in found) if k in watched} - finished)


def loop_ended(data_dir, now, out=print):
    """Stop an active loop whose Loop End has passed. True when it stopped."""
    loop = _read(_loop_file(data_dir), {})
    if not loop.get("active") or not loop.get("loopEnd") or now < datetime.fromisoformat(loop["loopEnd"]):
        return False
    _write(_loop_file(data_dir), {**loop, "active": False, "cron": None})
    out(f"CRON {loop['cron']}" if loop.get("cron") else "NO CRON")
    out(f"The loop reached its Loop End at {_local(loop['loopEnd'])} and stopped. "
        "**/orca-pr-review start** starts it again.")
    return True


def prune(data_dir, now):
    """Drop each finished entry whose finishedAt is more than recentWindowHours before `now`."""
    window = timedelta(hours=recent_window_hours(data_dir))
    for led in all_ledgers(data_dir):
        old = [n for n, e in led["prs"].items() if e.get("finishedAt") and now - datetime.fromisoformat(e["finishedAt"]) > window]
        for n in old:
            del led["prs"][n]
        if old:
            _write(ledger_path(data_dir, led["repo"]), led)


def tick(data_dir, out=print, now=None):
    now = now or datetime.now(timezone.utc)
    if loop_ended(data_dir, now, out):
        return
    prune(data_dir, now)
    watched = set(watched_repos(data_dir))
    # candidates() skips an unwatched repo, so a cleanup that failed during unwatch retries here.
    for led in all_ledgers(data_dir):
        left = {n: e for n, e in led["prs"].items() if e.get("worker") and not e.get("finishedAt")}
        if led["repo"] not in watched and left:
            for number, entry in left.items():
                _clean(led["repo"], number, entry, out)
            _write(ledger_path(data_dir, led["repo"]), led)
    me = gh("api", "user", "--jq", ".login").strip()
    ledgers = {}
    for repo, number in candidates(data_dir):
        if repo not in ledgers:
            led = read_ledger(data_dir, repo)
            cadence = timedelta(minutes=int(settings_for(data_dir, repo)["cadenceMinutes"]))
            # A repo with a slower cadence than the cron sits out the ticks in between.
            due = not led["scannedAt"] or now - datetime.fromisoformat(led["scannedAt"]) >= cadence - timedelta(seconds=30)
            ledgers[repo] = led if due else None
        led = ledgers[repo]
        if led is None:
            continue
        try:
            step(data_dir, led, number, me, out)
        except Fail as e:
            # One PR's failure never stops the rest, and the ledger saved so far keeps its posts.
            _say(led["prs"].get(str(number), {}), f"Skipped {repo}#{number} this tick: {e}. The next tick retries.", out)
        _write(ledger_path(data_dir, repo), led)
    for repo, led in ledgers.items():
        if led is not None:
            led["scannedAt"] = _now()
            _write(ledger_path(data_dir, repo), led)


def step(data_dir, led, number, me, out=print):
    """Read, classify and move one PR of a due repo; the tick saves the ledger after each."""
    repo = led["repo"]
    pr = json.loads(gh("pr", "view", str(number), "-R", repo, "--json", VIEW_FIELDS))
    action = classify(pr, me, led["prs"].get(str(number)))
    if action == "NEW":
        if not claim(repo, number, me):
            out(f"Backed off {repo}#{number}: another reviewer claimed it first.")
            return
        led["prs"][str(number)] = {
            "number": number, "title": pr["title"], "url": pr["url"], "author": pr["author"]["login"],
            "claimedAt": _now(), "headSha": None, "round": 0, "verdict": None, "worker": None, "harness": None, "draft": None,
        }
        out(f"Claimed {repo}#{number}: {pr['title']}. {pr['url']}")
    elif action == "CLAIMED" and str(number) in led["prs"] and led["prs"][str(number)]["verdict"] is None:
        # Someone else took a PR I had not posted on yet: my unposted review no longer applies.
        drop(data_dir, led, number, _logins(pr), out)
        return
    elif action == "FOLLOWUP":
        if not start_round(led, pr, out):
            return
    elif action != "INFLIGHT":
        entry = led["prs"].get(str(number))
        # Merged, closed or posted: leave no worktree or terminal behind.
        cleaned = not (entry and entry.get("worker")) or _clean(repo, number, entry, out)
        # A merged or closed PR never comes back: once nothing is left behind, its entry stays as history.
        if entry and cleaned and pr.get("state") != "OPEN":
            entry.update(finishedAt=_now(), state=pr.get("state"))
        return
    advance(data_dir, led, pr, me, out)


# --- Loop lifecycle --------------------------------------------------------

def _loop_file(data_dir):
    return Path(data_dir) / "pr-review" / "loop.json"


def _repo_root():
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return Path(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path.cwd()


def _terminal():
    """The Orca terminal handle this process runs in, or None outside Orca."""
    try:
        return json.loads(_run(orca_cli(), ["terminal", "show", "--json"], 10))["result"]["terminal"]["handle"]
    except (Fail, ValueError, KeyError, TypeError):
        return None


def register_run(data_dir, repo):
    """Upsert the loop into the Run Registry, keyed by the repo it started from."""
    runs = _read(Path(data_dir) / REGISTRY_FILE, {}).get("runs") or []
    runs = [r for r in runs if (r.get("repoPath"), r.get("workstream")) != (str(repo), WORKSTREAM)]
    runs.append({"repoPath": str(repo), "repoName": repo.name, "workstream": WORKSTREAM, "kind": "pr-review", "startedAt": _now()})
    _write(Path(data_dir) / REGISTRY_FILE, {"runs": runs, "updatedAt": _now()})


def _local(iso):
    return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _running(data_dir):
    """The user-facing line for a running loop."""
    loop = _read(_loop_file(data_dir), {})
    return (f"Watching {', '.join(watched_repos(data_dir))}: a scan every {loop.get('cadenceMinutes')} min until the "
            f"Loop End at {_local(loop['loopEnd'])}. The session cron expires after 7 days and ends when this session closes.")


def start(data_dir, repos=(), out=print):
    """No repos: print CHOOSE for the skill's question. With repos: watch exactly those and start the loop."""
    if not repos:
        current = repo_slug(_repo_root(), host="github.com")
        before = [r for r in sorted(_all_settings(data_dir)) if r != current]
        out(f"CHOOSE current={current or 'none'} before={','.join(before) or 'none'}")
        return
    repos = sorted({repo_key(data_dir, _check_repo(r)) for r in repos})
    save_settings(data_dir, {r: {"watched": r in repos} for r in {*watched_repos(data_dir), *repos}})
    loop = _read(_loop_file(data_dir), {})
    cadence = loop_cadence(data_dir)
    hours = max(settings_for(data_dir, r)["loopEndHours"] for r in repos)
    root = _repo_root()
    register_run(data_dir, root)
    end = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
    _write(_loop_file(data_dir), {**loop, "active": True, "cadenceMinutes": cadence, "startedAt": _now(),
                                  "loopEnd": end, "repoPath": str(root), "terminal": _terminal()})
    running = loop.get("active") and loop.get("cron")
    if running:
        out(f"RUNNING cron={loop['cron']}")
    out(f"CRON */{cadence} * * * *" if cadence < 60 else f"CRON 7 */{cadence // 60} * * *")
    if running:
        out(_running(data_dir))


def set_cron(data_dir, job, out=print):
    _write(_loop_file(data_dir), {**_read(_loop_file(data_dir), {}), "cron": job})
    out(_running(data_dir))


def stop(data_dir, out=print):
    loop = _read(_loop_file(data_dir), {})
    _write(_loop_file(data_dir), {**loop, "active": False, "cron": None})
    out(f"CRON {loop['cron']}" if loop.get("cron") else "NO CRON")
    out("The loop has stopped. **/orca-pr-review start** starts it again.")


def status(data_dir, out=print):
    loop = _read(_loop_file(data_dir), {})
    state = f"running every {loop.get('cadenceMinutes')} min" if loop.get("active") else "stopped"
    out(f"Loop: {state}.")
    rows = [(led["repo"], e) for led in all_ledgers(data_dir) for e in led["prs"].values() if not e.get("finishedAt")]
    if not rows:
        out("No PRs in the ledger.")
    for repo, e in sorted(rows, key=lambda r: (r[0], r[1]["number"])):
        out(f"- {repo}#{e['number']} {e['title']}: round {e['round']}, verdict {e['verdict'] or 'none'}. {e['url']}")


def _lock(data_dir):
    """An exclusive hold on pr-review/.lock for this process, or None while another holds it."""
    path = Path(data_dir) / "pr-review" / ".lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except BlockingIOError:
        f.close()
        return None


def main(argv):
    data = plugin_data_dir()
    cmd = argv[1] if len(argv) > 1 else None
    lock = None
    try:
        # tick, approve and feedback read, post and write the same ledger: one at a time.
        if cmd in ("tick", "approve", "feedback"):
            lock = _lock(data)
            if lock is None and cmd == "tick":
                return 0
            if lock is None:
                raise Fail("a tick, approve or feedback is running. Run the command again in a minute")
        if cmd == "start":
            start(data, argv[2:])
        elif cmd == "show" and len(argv) == 3:
            show(data, argv[2])
        elif cmd == "watch" and len(argv) >= 3:
            watch(data, argv[2], argv[3:])
        elif cmd == "unwatch" and len(argv) == 3:
            unwatch(data, argv[2])
        elif cmd == "set-cron" and len(argv) == 3:
            set_cron(data, argv[2])
        elif cmd == "tick":
            tick(data)
        elif cmd == "approve" and len(argv) == 3:
            approve(data, argv[2])
        elif cmd == "feedback" and len(argv) == 3:
            # On stdin, so the user's words reach the worker without shell escaping.
            feedback(data, argv[2], sys.stdin.read())
        elif cmd == "stop":
            stop(data)
        elif cmd == "status":
            status(data)
        else:
            raise Fail("usage: pr_review.py start [<owner/repo>...] | show <owner/repo> | watch <owner/repo> "
                       "[key=value ...] | unwatch <owner/repo> | set-cron <id> | tick | approve <owner/repo#n> | "
                       "feedback <owner/repo#n> < text | stop | status")
    except Fail as e:
        print(f"FAIL: {e}")
        return 1
    finally:
        if lock:
            lock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
