#!/usr/bin/env python3
"""Deterministic helpers for the pi-init skill.

Subcommands (all print JSON to stdout, diagnostics to stderr):
  preflight [--focus PATH]   resolve root, report <root>/AGENTS.md state and focus bounds
  inventory                  list high-signal evidence files that exist and are not ignored
  diff                       unified diff of stdin draft vs current AGENTS.md (writes nothing)
  write --expect-sha SHA     write stdin to AGENTS.md if it still matches preflight (or "absent")
  validate [--stdin]         static checks on AGENTS.md (or a stdin draft)

Exit codes: 0 ok, 1 blocking finding or refusal, 2 usage error.
Python 3.11+, standard library only. Run `pi_init.py --selftest` to check it.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TARGET = "AGENTS.md"

# Basename patterns. Manifests are matched up to two directories deep (workspaces);
# everything else is root-only unless its pattern contains a "/".
MANIFESTS = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "Cargo.toml", "go.mod",
    "Gemfile", "composer.json", "pom.xml", "build.gradle", "build.gradle.kts", "mix.exs",
    "deno.json", "deno.jsonc", "pnpm-workspace.yaml", "lerna.json", "nx.json", "turbo.json",
    "requirements.txt", "requirements-dev.txt", "go.work", "Pipfile",
}
CATEGORIES: dict[str, list[str]] = {
    "readme": ["README*", "readme*"],
    "lockfiles": [
        "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
        "poetry.lock", "uv.lock", "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock", "Pipfile.lock",
    ],
    "tooling": [
        "Makefile", "justfile", "Justfile", "Taskfile.yml", "Taskfile.yaml", "tsconfig*.json",
        ".eslintrc*", "eslint.config.*", ".prettierrc*", "prettier.config.*", "biome.json*",
        "ruff.toml", ".ruff.toml", "mypy.ini", "tox.ini", "noxfile.py", "pytest.ini",
        "jest.config.*", "vitest.config.*", "playwright.config.*", "vite.config.*",
        ".editorconfig", "Dockerfile", "docker-compose*.y*ml", "compose*.y*ml",
        ".tool-versions", ".nvmrc", ".python-version", "mise.toml", ".mise.toml",
    ],
    "ci": [
        ".github/workflows/*", ".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml",
        "Jenkinsfile", "bitbucket-pipelines.yml", ".buildkite/*",
    ],
    "hooks": [".pre-commit-config.yaml", ".husky/*", "lefthook.yml", "lefthook.yaml"],
    "scripts": ["scripts/*", "bin/*", "tools/*"],
    "agent_instructions": [
        "AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".windsurfrules", ".cursor/rules/*",
        ".github/copilot-instructions.md", ".claude/settings.json", ".pi/settings.json",
    ],
}
NESTED_INSTRUCTION_NAMES = {"AGENTS.md", "CLAUDE.md"}
WALK_SKIP = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__", "target"}


def _git(root: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], input=stdin, capture_output=True, text=True)


def resolve_root(override: str | None) -> tuple[Path, str]:
    if override:
        return Path(override).resolve(), "argument"
    try:
        out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve(), "git"
    except FileNotFoundError:
        pass
    return Path.cwd().resolve(), "cwd"


def is_git(root: Path) -> bool:
    try:
        return _git(root, "rev-parse", "--is-inside-work-tree").stdout.strip() == "true"
    except FileNotFoundError:
        return False


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_state(root: Path) -> dict:
    path = root / TARGET
    if path.is_symlink():
        kind = "symlink"
    elif not path.exists():
        kind = "absent"
    elif path.is_file():
        kind = "regular"
    else:
        kind = "other"
    git_status = None
    if is_git(root):
        porcelain = _git(root, "status", "--porcelain", "--", TARGET).stdout.strip()
        if porcelain:
            git_status = "untracked" if porcelain.startswith("??") else "dirty"
        elif kind != "absent":
            git_status = "clean"
    return {
        "path": str(path),
        "kind": kind,
        "sha256": sha256(path) if kind == "regular" else None,
        "git_status": git_status,
    }


def cmd_preflight(root: Path, source: str, focus: str | None) -> int:
    state = target_state(root)
    result = {"root": str(root), "root_source": source, "target": state, "focus": None, "blocking": []}
    if state["kind"] in ("symlink", "other"):
        result["blocking"].append(f"target is a {state['kind']}; leave it untouched")
    if focus is not None:
        fpath = (root / focus).resolve()
        in_bounds = fpath == root or root in fpath.parents
        result["focus"] = {"path": str(fpath), "in_bounds": in_bounds, "exists": fpath.exists()}
        if not in_bounds:
            result["blocking"].append("focus is outside the root; omit it")
    print(json.dumps(result, indent=2))
    return 1 if result["blocking"] else 0


def list_files(root: Path) -> list[str]:
    if is_git(root):
        out = _git(root, "ls-files", "--cached", "--others", "--exclude-standard")
        return sorted({line for line in out.stdout.splitlines() if (root / line).is_file()})
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in WALK_SKIP]
        for name in filenames:
            found.append(Path(dirpath, name).relative_to(root).as_posix())
    return sorted(found)


def classify(files: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {k: [] for k in ["manifests", *CATEGORIES, "nested_instructions"]}
    for rel in files:
        p = Path(rel)
        depth = len(p.parts) - 1
        if p.name in MANIFESTS and depth <= 2:
            result["manifests"].append(rel)
            continue
        if p.name in NESTED_INSTRUCTION_NAMES and depth > 0:
            result["nested_instructions"].append(rel)
            continue
        for cat, patterns in CATEGORIES.items():
            # Patterns with "/" match one directory level; bare patterns are root-only.
            if any(
                (depth == 0 and "/" not in pat and p.match(pat))
                or ("/" in pat and depth == pat.count("/") and p.match(pat))
                for pat in patterns
            ):
                result[cat].append(rel)
                break
    return result


def cmd_inventory(root: Path) -> int:
    print(json.dumps({"root": str(root), "git": is_git(root), "files": classify(list_files(root))}, indent=2))
    return 0


def read_stdin() -> str:
    text = sys.stdin.read()
    return text if text.endswith("\n") else text + "\n"


def cmd_diff(root: Path) -> int:
    path = root / TARGET
    if path.is_symlink() or (path.exists() and not path.is_file()):
        print(json.dumps({"error": "target is not a regular file"}))
        return 1
    old = path.read_text().splitlines(keepends=True) if path.exists() else []
    new = read_stdin().splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(old, new, f"a/{TARGET}", f"b/{TARGET}"))
    print(json.dumps({"changed": bool(diff), "diff": diff}, indent=2))
    return 0


def cmd_write(root: Path, expect: str) -> int:
    path = root / TARGET
    state = target_state(root)
    current = "absent" if state["kind"] == "absent" else state["sha256"]
    if state["kind"] in ("symlink", "other"):
        reason = f"target is a {state['kind']}"
    elif current != expect:
        reason = f"target changed since preflight (expected {expect}, found {current})"
    else:
        reason = None
    content = read_stdin()
    if reason is None and not content.strip():
        reason = "refusing to write empty content"
    if reason:
        print(json.dumps({"written": False, "reason": reason}))
        return 1
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".AGENTS.md.")
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    if path.exists():
        os.chmod(tmp, path.stat().st_mode & 0o777)
    else:
        os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    print(json.dumps({"written": True, "path": str(path), "sha256": sha256(path)}))
    return 0


CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+\S")
FENCE = re.compile(r"^\s*(```|~~~)")


def looks_like_path(token: str) -> bool:
    if " " in token or any(c in token for c in "*<>{}$|=") or "://" in token or token.startswith("-"):
        return False
    return "/" in token or bool(re.search(r"\.[A-Za-z0-9]{1,5}$", token))


def validate_text(text: str, root: Path) -> list[dict]:
    findings = []
    lines = text.splitlines()
    in_fence = False
    headings: list[tuple[int, int]] = []  # (line index, level)
    if not text.strip():
        findings.append({"line": 0, "issue": "file is empty"})
    for i, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if m := HEADING.match(line):
            headings.append((i, len(m.group(1))))
        candidates = [t for t in CODE_SPAN.findall(line) if looks_like_path(t)]
        candidates += [u.split("#")[0] for u in LINK.findall(line) if "://" not in u and not u.startswith(("#", "mailto:"))]
        for token in candidates:
            if not token:
                continue
            resolved = (root / token).resolve()
            if not (resolved == root or root in resolved.parents):
                findings.append({"line": i + 1, "issue": f"path leaves the root: {token}"})
            elif not resolved.exists():
                findings.append({"line": i + 1, "issue": f"path does not exist: {token}"})
    if in_fence:
        findings.append({"line": len(lines), "issue": "unclosed code fence"})
    # A heading is empty when the next heading at the same or higher level follows with no content between.
    for n, (idx, level) in enumerate(headings):
        end = len(lines)
        for nxt_idx, nxt_level in headings[n + 1:]:
            if nxt_level <= level:
                end = nxt_idx
                break
        body = [ln for ln in lines[idx + 1:end] if ln.strip()]
        if not body:
            findings.append({"line": idx + 1, "issue": f"empty heading: {lines[idx].strip()}"})
    return findings


def cmd_validate(root: Path, use_stdin: bool) -> int:
    if use_stdin:
        text = sys.stdin.read()
    else:
        path = root / TARGET
        if not path.is_file() or path.is_symlink():
            print(json.dumps({"error": "AGENTS.md is missing or not a regular file"}))
            return 1
        text = path.read_text()
    findings = validate_text(text, root)
    print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
    return 1 if findings else 0


def selftest() -> int:
    import contextlib
    import io

    def run(fn, *args, stdin: str = "") -> tuple[int, dict]:
        out = io.StringIO()
        old_in = sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out):
                code = fn(*args)
        finally:
            sys.stdin = old_in
        return code, json.loads(out.getvalue())

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text("secret.env\n")
        for rel in ["README.md", "package.json", "pnpm-lock.yaml", ".github/workflows/ci.yml",
                    "packages/a/package.json", "packages/a/AGENTS.md", "secret.env", "src/index.ts"]:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("x\n")

        code, pre = run(cmd_preflight, root, "argument", "src")
        assert code == 0 and pre["target"]["kind"] == "absent" and pre["focus"]["in_bounds"], pre
        code, pre = run(cmd_preflight, root, "argument", "../elsewhere")
        assert code == 1 and not pre["focus"]["in_bounds"], pre

        code, inv = run(cmd_inventory, root)
        files = inv["files"]
        assert files["manifests"] == ["package.json", "packages/a/package.json"], files
        assert files["lockfiles"] == ["pnpm-lock.yaml"] and files["ci"] == [".github/workflows/ci.yml"], files
        assert files["nested_instructions"] == ["packages/a/AGENTS.md"], files
        assert "secret.env" not in json.dumps(files), files

        draft = "# Project\n\nRun `pnpm test`. See `packages/a/AGENTS.md` for package rules.\n"
        code, d = run(cmd_diff, root, stdin=draft)
        assert code == 0 and d["changed"] and "+# Project" in d["diff"], d
        code, w = run(cmd_write, root, "deadbeef", stdin=draft)
        assert code == 1 and not w["written"], w
        code, w = run(cmd_write, root, "absent", stdin=draft)
        assert code == 0 and w["written"], w
        assert run(cmd_write, root, "absent", stdin=draft)[0] == 1  # stale guard: file now exists
        code, pre = run(cmd_preflight, root, "argument", None)
        assert pre["target"]["sha256"] == w["sha256"] and pre["target"]["git_status"] == "untracked", pre
        code, d = run(cmd_diff, root, stdin=draft)
        assert not d["changed"], d

        code, v = run(cmd_validate, root, False)
        assert code == 0 and v["ok"], v
        bad = "# A\n## Empty\n## Full\ntext `docs/missing.md` and [x](../out.md)\n```\n`ignored/in/fence.md`\n```\n"
        code, v = run(cmd_validate, root, True, stdin=bad)
        issues = [f["issue"] for f in v["findings"]]
        assert code == 1 and "empty heading: ## Empty" in issues, issues
        assert "path does not exist: docs/missing.md" in issues and "path leaves the root: ../out.md" in issues, issues
        assert not any("fence.md" in i for i in issues), issues

        (root / TARGET).unlink()
        (root / TARGET).symlink_to(root / "README.md")
        code, pre = run(cmd_preflight, root, "argument", None)
        assert code == 1 and pre["target"]["kind"] == "symlink", pre
        assert run(cmd_write, root, "absent", stdin=draft)[0] == 1
    print("selftest ok", file=sys.stderr)
    return 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", help="override root resolution (default: git root, else cwd)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--focus", help="optional focus path, relative to the root")
    sub.add_parser("inventory")
    sub.add_parser("diff")
    p = sub.add_parser("write")
    p.add_argument("--expect-sha", required=True, help='sha256 from preflight, or "absent"')
    p = sub.add_parser("validate")
    p.add_argument("--stdin", action="store_true", help="validate a draft from stdin instead of the file")
    args = parser.parse_args(argv)
    root, source = resolve_root(args.root)
    if args.cmd == "preflight":
        return cmd_preflight(root, source, args.focus)
    if args.cmd == "inventory":
        return cmd_inventory(root)
    if args.cmd == "diff":
        return cmd_diff(root)
    if args.cmd == "write":
        return cmd_write(root, args.expect_sha)
    return cmd_validate(root, args.stdin)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
