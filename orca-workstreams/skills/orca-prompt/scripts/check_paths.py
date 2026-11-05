"""List every path, script and command a Workstream names that does not exist.

The first half of the Prompt Check. Reads `_plan.md` and every `*.prompt.md` in
the Workstream directory, takes each inline code span and each fenced code line,
and reports:

- a path (it holds a `/` or ends in a file extension) that exists neither from
  the repo root, nor from the Workstream directory or its `_completed/`, nor as
  the tail of any file in the repo, so `orca-prompt/SKILL.md` and `SKILL.md`
  both pass;
- a command whose program (`python3`, `pnpm`, `gh`, ...) is not on PATH.

Spans holding a placeholder (`<`, `{`, `$`, `*`) or a scheme (`https:`) name no
one file and are skipped. So are slash commands and routes (`/clear`,
`/api/board`), `owner/repo` pairs with no extension whose first part is not in
the repo, and the files a run writes later (`_status.json`, `_rules.md`). A path a
Work Item creates shows up as missing too: the orca-prompt session reads the
list and fixes only the real gaps.

Usage:
    python3 check_paths.py <workstream-dir>   # one FAIL: line per missing name, exit 1 if any
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

SPAN = re.compile(r"`([^`\n]+)`")
EXTENSION = re.compile(r"\.(py|md|json|ts|tsx|js|mjs|sh|toml|ya?ml|html|css|txt)$")
# A span names a command only when it starts with one of these, so `main` or `pr-merge` never reads as one.
PROGRAMS = {"python3", "python", "node", "bash", "sh", "pnpm", "npm", "npx", "uv", "git", "gh", "orca", "claude", "rtk", "codegraph"}
SKIP = re.compile(r"[<>{}$*]|^#")
# Written by scaffold.py or during the run, so a fresh Workstream lacks them.
RUNTIME = {"_status.json", "_prompt-band.json", "_rules.md", "_decisions.md", "_review.prompt.md", "_plan-gate.prompt.md"}


def repo_root(start):
    r = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else Path(start).resolve()


def repo_files(root):
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard"], capture_output=True, text=True)
    return ["/" + p for p in r.stdout.splitlines()]


def in_repo(token, files):
    """True when some repo file is `token`, ends with it, or sits under it as a directory."""
    t = "/" + token.strip("/")
    return any(f.endswith(t) or t + "/" in f for f in files)


def candidates(text):
    """Yield (line number, token, is the token a program) for every name worth checking."""
    fenced = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        for span in ([line.strip()] if fenced else SPAN.findall(line)):
            words = span.split()
            if not words:
                continue
            if words[0] in PROGRAMS:
                yield n, words[0], True
                words = words[1:]
            elif len(words) > 1:
                continue  # prose in backticks, or a command run by a program not listed
            for word in words:
                word = re.sub(r":\d+$", "", word.strip("'\",;:()").rstrip(".:"))  # drop a `file.py:42` line number
                if word and not word.startswith("-") and not SKIP.search(word) and ":" not in word and ("/" in word or EXTENSION.search(word)):
                    yield n, word, False


def missing(workstream_dir):
    """Return `FAIL:` lines, one per missing name; empty means every name exists."""
    workstream_dir = Path(workstream_dir)
    root = repo_root(workstream_dir)
    files = None
    problems = []
    for f in [workstream_dir / "_plan.md", *sorted(workstream_dir.glob("*.prompt.md"))]:
        if not f.exists():
            continue
        for n, token, is_program in candidates(f.read_text()):
            if is_program:
                if not shutil.which(token):
                    problems.append(f"FAIL: {f.name}:{n}: command {token} is not on PATH")
                continue
            p = Path(token).expanduser()
            first = Path(*p.parts[:2]) if p.is_absolute() else Path(p.parts[0])
            if p.name in RUNTIME or (root / p).exists() or (workstream_dir / p).exists() or (workstream_dir / "_completed" / p.name).exists():
                continue
            if p.is_absolute() and not first.exists():
                continue  # a slash command or route, not a file on this machine
            if "/" in token and not EXTENSION.search(token) and not token.startswith(".") and not (root / first).exists():
                continue  # owner/repo, provider/model
            files = repo_files(root) if files is None else files
            if not p.is_absolute() and in_repo(token, files):
                continue
            problems.append(f"FAIL: {f.name}:{n}: path {token} does not exist")
    return problems


def main(argv):
    if len(argv) != 2 or not Path(argv[1]).is_dir():
        print("FAIL: usage: check_paths.py <workstream-dir>")
        return 2
    problems = missing(argv[1])
    print("\n".join(problems) or "ok: every named path and command exists")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
