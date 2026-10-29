#!/usr/bin/env python3
"""Self-check for kb.py. Run: python3 test_kb.py"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KB = Path(__file__).resolve().parent / "kb.py"

DECISIONS = """# Decision Log

What the Main Orchestrator decided and learned during this Workstream, oldest first.

### 2026-10-01 · Board binds to 127.0.0.1

A LAN bind exposed the token page.

### 2026-10-02 · Wave 1 retro

No failures.
"""

EXTRACTION = {
    "nodes": [
        {"name": "Wave Band", "type": "SYSTEM", "description": "Draws each Work Item's progress"},
        {"name": "Status File", "type": "DOCUMENT", "description": "_status.json, polled every 2 s"},
    ],
    "edges": [{"source": "Wave Band", "predicate": "depends_on", "target": "Status File"}],
    "aliases": [{"entity": "Status File", "alias": "_status.json"}, {"entity": "Wave Band", "alias": "band"}],
}


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def setup(tmp):
    home, repo = Path(tmp) / "home", Path(tmp) / "repo"
    home.mkdir()
    log = repo / ".orca" / "prompts" / "demo-ws" / "_decisions.md"
    log.parent.mkdir(parents=True)
    log.write_text(DECISIONS)
    git(repo, "init", "-q")
    git(repo, "remote", "add", "origin", "git@github.com:acme/widgets.git")
    git(repo, "add", ".")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return home, repo


def run(home, repo, *args):
    env = dict(os.environ, HOME=str(home))
    return subprocess.run([sys.executable, str(KB), "--repo", str(repo), *args], capture_output=True, text=True, env=env)


def test_bootstrap_backfills_into_temp_home():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        r = run(home, repo, "bootstrap")
        assert r.returncode == 0, r.stdout + r.stderr
        root = home / ".claude" / "orca-helpers" / "kb" / "acme__widgets"
        assert (root / "graph.db").is_file()
        assert (root / "pages" / "decisions__demo-ws.md").read_text() == DECISIONS
        doc = json.loads((root / "extraction" / "decisions__demo-ws.json").read_text())
        assert [n["name"] for n in doc["nodes"]] == ["demo-ws", "demo-ws: Board binds to 127.0.0.1", "demo-ws: Wave 1 retro"]
        # Nothing writes inside the repo.
        status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--ignored"], capture_output=True, text=True)
        assert status.stdout == "", status.stdout
        # The backfill is recallable by the Workstream's alias.
        r = run(home, repo, "review", "what did the demo ws decide?")
        assert "demo-ws: Board binds to 127.0.0.1 --[part_of]--> demo-ws" in r.stdout, r.stdout
        assert "A LAN bind exposed the token page." in r.stdout, r.stdout
        # Rerunning rewrites the same files rather than duplicating them.
        assert run(home, repo, "bootstrap").returncode == 0
        assert len(list((root / "extraction").glob("*.json"))) == 1


def test_two_workstreams_keep_their_own_wave_1_retro():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        other = repo / ".orca" / "prompts" / "other-ws" / "_decisions.md"
        other.parent.mkdir()
        other.write_text(DECISIONS.replace("No failures.", "Two NO-SHIPs."))
        assert run(home, repo, "bootstrap").returncode == 0
        # The bare title is an alias, so one task recalls both entries, each with its own text.
        r = run(home, repo, "review", "what did the Wave 1 retro say?")
        assert "demo-ws: Wave 1 retro: 2026-10-02: No failures." in r.stdout, r.stdout
        assert "other-ws: Wave 1 retro: 2026-10-02: Two NO-SHIPs." in r.stdout, r.stdout
        assert run(home, repo, "lint").stdout.strip() == "kb clean"


def test_parallel_updates_never_crash_and_recall_keeps_answering():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        assert run(home, repo, "bootstrap").returncode == 0
        env = dict(os.environ, HOME=str(home))
        writers = [subprocess.Popen([sys.executable, str(KB), "--repo", str(repo), "update", f"page-{i}", "--page", f"# Page {i}",
                                     "--extraction", json.dumps(EXTRACTION)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                   for i in range(10)]
        while any(w.poll() is None for w in writers):
            r = run(home, repo, "review", "what did the demo ws decide?")
            assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr
            assert "demo-ws: Board binds to 127.0.0.1" in r.stdout, r.stdout
        for w in writers:
            out, err = w.communicate()
            assert w.returncode == 0 and err == "", out + err
        root = home / ".claude" / "orca-helpers" / "kb" / "acme__widgets"
        assert not list(root.rglob("*.tmp")), list(root.rglob("*.tmp"))
        assert run(home, repo, "lint").stdout.strip() == "kb clean"


def test_one_word_workstream_lints_clean():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        (repo / ".orca" / "prompts" / "demo-ws").rename(repo / ".orca" / "prompts" / "orca")
        assert run(home, repo, "bootstrap").returncode == 0
        r = run(home, repo, "lint")
        assert r.stdout.strip() == "kb clean", r.stdout


def test_update_with_aliases_then_recall_by_alias():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        r = run(home, repo, "update", "wave-band", "--page", "# Wave Band\n\nIt polls _status.json.", "--extraction", json.dumps(EXTRACTION))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "2 entities, 1 relations, 2 aliases" in r.stdout, r.stdout
        # "band" is an alias only: the name "Wave Band" is not in the task.
        r = run(home, repo, "review", "change how the band", "draws")
        assert "Wave Band --[depends_on]--> Status File" in r.stdout, r.stdout
        assert run(home, repo, "lint").stdout.strip() == "kb clean"


def test_update_refuses_a_write_without_aliases_or_with_a_bad_type():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        bare = dict(EXTRACTION, aliases=[])
        r = run(home, repo, "update", "x", "--page", "# X", "--extraction", json.dumps(bare))
        assert r.returncode == 1 and "no aliases" in r.stdout, r.stdout
        bad = dict(EXTRACTION, nodes=[{"name": "Wave Band", "type": "WIDGET"}])
        r = run(home, repo, "update", "x", "--page", "# X", "--extraction", json.dumps(bad))
        assert r.returncode == 1 and "WIDGET" in r.stdout, r.stdout
        assert not (home / ".claude" / "orca-helpers" / "kb" / "acme__widgets" / "pages" / "x.md").exists()


def test_lint_is_read_only_and_reports_problems():
    with tempfile.TemporaryDirectory() as tmp:
        home, repo = setup(tmp)
        assert "run /orca-bootstrap" in run(home, repo, "lint").stdout
        run(home, repo, "bootstrap")
        root = home / ".claude" / "orca-helpers" / "kb" / "acme__widgets"
        (root / "pages" / "orphan.md").write_text("# Orphan\n")
        before = (root / "graph.db").read_bytes()
        r = run(home, repo, "lint")
        assert r.returncode == 1 and "pages/orphan.md has no extraction" in r.stdout, r.stdout
        assert (root / "graph.db").read_bytes() == before


def test_repo_key_keeps_the_dir_name_for_a_trailing_slash_origin():
    sys.path.insert(0, str(KB.parent))
    from kb import repo_key
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "widgets"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        for url, key in (("https://github.com/acme/widgets/", "widgets"), ("https://github.com/acme/widgets.git", "acme__widgets"),
                         ("git@github.com:acme/widgets.git", "acme__widgets")):
            subprocess.run(["git", "-C", str(repo), "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)
            assert repo_key(repo) == key, url


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok {name}")
