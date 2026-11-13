#!/usr/bin/env python3
"""The Orca Knowledge Graph: one user-level store per repo (ADR 0015).

    python3 kb.py bootstrap [--repo DIR]
    python3 kb.py review <task words...> [--repo DIR]
    python3 kb.py update <slug> --page <markdown> --extraction <json> [--repo DIR]
    python3 kb.py lint [--repo DIR]

The store is `~/.claude/orca-helpers/kb/<owner__repo>/`: `pages/<slug>.md`,
`extraction/<slug>.json` and `graph.db`, rebuilt from the extraction on every
write. Nothing here writes inside the repo.

Exit codes: 0 clean, 1 a problem was reported, 2 usage error.
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_graph import ENTITY_TYPES, PREDICATES, build  # noqa: E402
from recall import recall  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "orca-prompt" / "scripts"))
from scaffold import repo_slug, write_text_atomic  # noqa: E402

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
ENTRY_RE = re.compile(r"^### (?P<date>\S+) · (?P<title>[^\n]+)\n(?P<body>.*?)(?=^### |\Z)", re.DOTALL | re.MULTILINE)


class KbError(Exception):
    pass


def repo_key(repo):
    """`owner__repo` from the repo's origin remote, else the directory name."""
    slug = repo_slug(repo)
    return slug.replace("/", "__") if slug else Path(repo).resolve().name


def store(repo):
    return Path.home() / ".claude" / "orca-helpers" / "kb" / repo_key(repo)


def rebuild(root):
    counts, problems = build(root / "extraction", root / "graph.db")
    return counts, problems


def check_extraction(doc):
    """Problems in one extraction before it lands, so a bad write never reaches the store."""
    problems = []
    names = set()
    for node in doc.get("nodes", []):
        if not node.get("name"):
            problems.append("a node has no name")
        if node.get("type") not in ENTITY_TYPES:
            problems.append(f"node {node.get('name')!r} has type {node.get('type')!r}; use one of {', '.join(ENTITY_TYPES)}")
        names.add(node.get("name"))
    for edge in doc.get("edges", []):
        if edge.get("predicate") not in PREDICATES:
            problems.append(f"edge {edge.get('source')!r} -> {edge.get('target')!r} has predicate {edge.get('predicate')!r}; use one of {', '.join(PREDICATES)}")
    if not doc.get("nodes"):
        problems.append("the extraction has no nodes")
    if not doc.get("edges"):
        problems.append("the extraction has no edges, so recall can never return it")
    # ADR 0015: recall seeds on literal names only, so every write carries aliases.
    if not doc.get("aliases"):
        problems.append("the extraction has no aliases; add the words a task would use for each node")
    return problems


def write(root, slug, page, doc):
    (root / "pages").mkdir(parents=True, exist_ok=True)
    (root / "extraction").mkdir(parents=True, exist_ok=True)
    doc = dict(doc, source_doc=f"pages/{slug}.md")
    write_text_atomic(root / "pages" / f"{slug}.md", page.rstrip("\n") + "\n", f"{slug}.md.")
    write_text_atomic(root / "extraction" / f"{slug}.json", json.dumps(doc, indent=2, sort_keys=True) + "\n", f"{slug}.json.")


def update(repo, slug, page, extraction):
    if not SLUG_RE.match(slug):
        raise KbError(f"slug {slug!r} must be lowercase letters, digits, '.', '_' or '-'")
    if not page.strip():
        raise KbError("the page is empty")
    try:
        doc = json.loads(extraction)
    except ValueError as exc:
        raise KbError(f"the extraction is not valid JSON: {exc}")
    if not isinstance(doc, dict):
        raise KbError("the extraction must be a JSON object with nodes, edges and aliases")
    problems = check_extraction(doc)
    if problems:
        raise KbError("; ".join(problems))
    root = store(repo)
    write(root, slug, page, doc)
    return root, rebuild(root)


def decision_doc(workstream, text):
    """One extraction for a Workstream's Decision Log: each entry part_of the Workstream.

    Entry nodes are named `<workstream>: <title>` because the graph merges nodes by
    name, so two Workstreams' "Wave 1 retro" would otherwise collapse into one.
    The bare title stays an alias, so a task naming it still seeds every match.
    """
    nodes = [{"name": workstream, "type": "PROCESS", "description": f"Orca Workstream {workstream}"}]
    edges = []
    aliases = [{"entity": workstream, "alias": workstream.replace("-", " ")}]
    for m in ENTRY_RE.finditer(text):
        title = m["title"].strip()
        name = f"{workstream}: {title}"
        body = " ".join(m["body"].split())
        nodes.append({"name": name, "type": "CONCEPT", "description": f"{m['date']}: {body}"})
        edges.append({"source": name, "predicate": "part_of", "target": workstream})
        aliases.append({"entity": name, "alias": title})
    return {"nodes": nodes, "edges": edges, "aliases": aliases}


def bootstrap(repo):
    """Create the store and backfill it from every `.orca/prompts/*/_decisions.md`. Rerunning rewrites the same files."""
    root = store(repo)
    for sub in ("pages", "extraction"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    backfilled = []
    for log in sorted(Path(repo).glob(".orca/prompts/*/_decisions.md")):
        workstream = log.parent.name
        text = log.read_text(encoding="utf-8")
        doc = decision_doc(workstream, text)
        if len(doc["nodes"]) == 1:
            continue  # a log with no entries yet has nothing to recall
        write(root, f"decisions__{workstream}", text, doc)
        backfilled.append(workstream)
    return root, backfilled, rebuild(root)


def lint(repo):
    """Read-only health check. Builds into a temp db so the store's graph.db is untouched."""
    root = store(repo)
    if not root.is_dir():
        return [f"no store at {root}: run /orca-bootstrap"]
    problems = []
    pages = {p.stem for p in (root / "pages").glob("*.md")}
    extracted = {p.stem for p in (root / "extraction").glob("*.json")}
    problems += [f"pages/{s}.md has no extraction" for s in sorted(pages - extracted)]
    problems += [f"extraction/{s}.json has no page" for s in sorted(extracted - pages)]
    with tempfile.TemporaryDirectory() as tmp:
        _, built = build(root / "extraction", Path(tmp) / "graph.db")
    problems += built
    if not (root / "graph.db").is_file():
        problems.append("graph.db is missing: run any update or /orca-bootstrap to rebuild it")
    for path in sorted((root / "extraction").glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue  # build already reported it
        aliased = {a.get("entity") for a in doc.get("aliases", [])}
        bare = [n["name"] for n in doc.get("nodes", []) if n.get("name") not in aliased and n.get("type") != "CONCEPT"]
        if bare:
            problems.append(f"{path.name}: no alias for {', '.join(bare)}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="the repo whose store to use (default: .)")
    verbs = parser.add_subparsers(dest="verb", required=True)
    verbs.add_parser("bootstrap")
    verbs.add_parser("lint")
    review = verbs.add_parser("review")
    review.add_argument("task", nargs="+")
    up = verbs.add_parser("update")
    up.add_argument("slug")
    up.add_argument("--page", required=True, help="the page's Markdown")
    up.add_argument("--extraction", required=True, help="JSON: {nodes, edges, aliases}")
    args = parser.parse_args(argv)

    try:
        if args.verb == "bootstrap":
            root, backfilled, (counts, problems) = bootstrap(args.repo)
            print(f"store {root}: backfilled {len(backfilled)} Decision Log(s) {', '.join(backfilled)}".rstrip())
        elif args.verb == "update":
            root, (counts, problems) = update(args.repo, args.slug, args.page, args.extraction)
            print(f"wrote pages/{args.slug}.md and extraction/{args.slug}.json in {root}")
        elif args.verb == "review":
            print(recall(" ".join(args.task), store(args.repo) / "graph.db").as_text())
            return 0
        else:
            problems = lint(args.repo)
            print("\n".join(problems) if problems else "kb clean")
            return 1 if problems else 0
    except KbError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(f"graph: {counts['entities']} entities, {counts['relations']} relations, {counts['aliases']} aliases")
    for p in problems:
        print(f"  {p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
