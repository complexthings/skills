#!/usr/bin/env python3
# Copied from .claude/skills/rex-kb-update/scripts/build_graph.py (ADR 0015).
"""Compile the Rex knowledge base's extraction JSON into a SQLite graph.

Deterministic: the same extraction files produce the same database, byte for
byte, because every node id is `uuid5` over its type and its normalised name
rather than a counter or an insertion order.

Two passes. Pass one loads every node from every document, so pass two can
resolve an edge whose endpoint is defined in a document it has not read yet --
`governance/sops.md` names the Release Process that `operational/deployments.md`
defines, and neither document is wrong. An edge whose endpoint resolves to
nothing is reported, never dropped silently: a missing endpoint is an extraction
bug, and a silent drop is that bug made invisible.

The vocabulary is closed (ADR-0030). A node or edge naming a type or predicate
outside it is reported and not loaded, so a bad extraction fails at build time
rather than surfacing as a fact that quietly never appears in a walk.

The database is never committed (ADR-0028): it is derived from files that are,
it conflicts on every concurrent edit, and it reviews as an opaque blob.

Standard library only, Python 3.9 floor (ADR-0012, ADR-0025).

Exit codes: 0 built clean, 1 an extraction problem was reported, 2 usage error.
"""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

# ADR-0030. These two tuples and `extract-prompt.md` must agree exactly; the
# selftest asserts it, because a mismatch here is invisible until a model in
# somebody else's repository emits a type this file then refuses to load.
ENTITY_TYPES = (
    "CONCEPT",
    "DOCUMENT",
    "KPI",
    "PERSON",
    "PROCESS",
    "ROLE",
    "SOP",
    "SYSTEM",
)
PREDICATES = (
    "depends_on",
    "governs",
    "held_by",
    "measured_by",
    "owned_by",
    "part_of",
    "references",
    "supports",
)

DEFAULT_EXTRACTION = Path(".agents") / "project-knowledge" / "graph" / "extraction"
DEFAULT_DB = Path(".agents") / "project-knowledge" / "graph" / "graph.db"

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def normalise(name):
    """Fold a name to its lookup key. Two spellings of one thing collide here."""
    return " ".join(str(name).lower().split()).replace(" ", "_")


def entity_id(type_, name):
    """`uuid5` over type and normalised name: no counter, no lookup, no model."""
    return str(uuid.uuid5(uuid.NAMESPACE_OID, "%s:%s" % (type_, normalise(name))))


def build(extraction_dir, db_path, schema_path=SCHEMA):
    """Compile every `*.json` under `extraction_dir` into `db_path`.

    Returns `(counts, problems)` -- counts keyed by table name, problems a list
    of human-readable strings, empty when the extraction is clean.
    """
    files = sorted(Path(extraction_dir).glob("*.json"))
    docs = []
    problems = []
    for path in files:
        try:
            docs.append(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            problems.append("%s: not valid JSON (%s)" % (path.name, exc))

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Build beside db_path and os.replace it over, so a reader never sees a missing
    # or half-built graph and parallel builds never unlink each other's file.
    # shortcut: no lock, so of two parallel builds the last replace wins even if
    # its snapshot missed the other's extraction; add a lock if that loses facts.
    fd, tmp = tempfile.mkstemp(dir=str(db_path.parent), prefix=db_path.name + ".", suffix=".tmp")
    os.close(fd)
    try:
        counts = _fill(sqlite3.connect(tmp), docs, problems, schema_path)
        os.replace(tmp, str(db_path))
    except BaseException:
        os.unlink(tmp)
        raise
    return counts, problems


def _fill(db, docs, problems, schema_path):
    db.executescript(Path(schema_path).read_text(encoding="utf-8"))

    # Pass 1 -- every node from every document, content-addressed.
    for doc in docs:
        source = doc.get("source_doc", "(unnamed)")
        for node in doc.get("nodes", []):
            type_ = node.get("type")
            if type_ not in ENTITY_TYPES:
                problems.append(
                    "%s: node %r has type %r, outside the ADR-0030 vocabulary"
                    % (source, node.get("name"), type_)
                )
                continue
            db.execute(
                "INSERT OR IGNORE INTO entities VALUES (?,?,?,?,?)",
                (
                    entity_id(type_, node["name"]),
                    node["name"],
                    type_,
                    node.get("description", ""),
                    source,
                ),
            )

    by_name = {}
    for eid, name in db.execute("SELECT id, name FROM entities"):
        by_name[normalise(name)] = eid

    # Pass 2 -- edges and aliases, endpoints resolved by normalised name.
    for doc in docs:
        source = doc.get("source_doc", "(unnamed)")
        for edge in doc.get("edges", []):
            predicate = edge.get("predicate")
            if predicate not in PREDICATES:
                problems.append(
                    "%s: edge %r --[%r]--> %r uses a predicate outside the "
                    "ADR-0030 vocabulary"
                    % (source, edge.get("source"), predicate, edge.get("target"))
                )
                continue
            src = by_name.get(normalise(edge.get("source", "")))
            tgt = by_name.get(normalise(edge.get("target", "")))
            if src and tgt:
                db.execute(
                    "INSERT INTO relations VALUES (?,?,?,?)",
                    (src, tgt, predicate, source),
                )
            else:
                missing = []
                if not src:
                    missing.append(repr(edge.get("source")))
                if not tgt:
                    missing.append(repr(edge.get("target")))
                problems.append(
                    "%s: skipped edge %r --[%s]--> %r, no node named %s"
                    % (
                        source,
                        edge.get("source"),
                        predicate,
                        edge.get("target"),
                        " or ".join(missing),
                    )
                )
        for alias in doc.get("aliases", []):
            eid = by_name.get(normalise(alias.get("entity", "")))
            if eid:
                db.execute("INSERT INTO aliases VALUES (?,?)", (eid, alias["alias"]))
            else:
                problems.append(
                    "%s: skipped alias %r, no node named %r"
                    % (source, alias.get("alias"), alias.get("entity"))
                )

    db.commit()
    counts = {}
    for table in ("entities", "relations", "aliases"):
        counts[table] = db.execute(
            "SELECT COUNT(*) FROM %s" % table  # table name is a literal above
        ).fetchone()[0]
    counts["documents"] = len(docs)
    db.close()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--extraction",
        default=str(DEFAULT_EXTRACTION),
        help="directory of extraction JSON (default: %s)" % DEFAULT_EXTRACTION,
    )
    parser.add_argument(
        "--db", default=str(DEFAULT_DB), help="database to write (default: %s)" % DEFAULT_DB
    )
    parser.add_argument("--selftest", action="store_true", help="run the selftest and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    extraction = Path(args.extraction)
    if not extraction.is_dir():
        print("no extraction directory at %s" % extraction, file=sys.stderr)
        return 2

    counts, problems = build(extraction, args.db)
    print(
        "built %s: %d entities, %d relations, %d aliases from %d documents"
        % (
            args.db,
            counts["entities"],
            counts["relations"],
            counts["aliases"],
            counts["documents"],
        )
    )
    for problem in problems:
        print("  %s" % problem, file=sys.stderr)
    return 1 if problems else 0


# --- selftest ----------------------------------------------------------------

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "rex-graph"


def _selftest():
    """Build the committed fixture, then drive the failure paths in a temp dir."""
    import tempfile

    checks = 0

    # The vocabulary in this file and the vocabulary in the prompt a model runs
    # are the one pair nothing else can check. The prompt does not ship with the
    # bundled copy of this script, so only assert when it is next door.
    prompt = Path(__file__).resolve().parent / "extract-prompt.md"
    if prompt.is_file():
        text = prompt.read_text(encoding="utf-8")
        for token in ENTITY_TYPES + PREDICATES:
            assert "`%s`" % token in text, "extract-prompt.md never names %s" % token
        # And nothing extra: a token in the prompt that this file rejects is the
        # same bug pointing the other way.
        import re

        quoted = set(re.findall(r"`([A-Za-z_]+)`", text))
        upper = set(t for t in quoted if t.isupper())
        assert upper == set(ENTITY_TYPES), upper ^ set(ENTITY_TYPES)
        checks += 1

    # The committed fixture is the richest corpus there is -- every type and
    # every predicate at least once -- but a bundled copy of this script sits
    # inside an installed skill with no `.agents/fixtures/` above it. Where it is
    # unreachable the temp-directory checks below still run, including the two
    # that matter most: a cross-document edge, and determinism.
    if FIXTURE.is_dir():
      with tempfile.TemporaryDirectory() as tmp:
          db = Path(tmp) / "graph.db"
          counts, problems = build(FIXTURE / "extraction", db)
          assert problems == [], problems
          assert counts == {
              "entities": 12,
              "relations": 11,
              "aliases": 5,
              "documents": 6,
          }, counts
          checks += 1

          # Every type and every predicate is exercised by the fixture. A type no
          # document uses is a type whose extraction rules nothing checks.
          conn = sqlite3.connect(str(db))
          types = set(row[0] for row in conn.execute("SELECT DISTINCT type FROM entities"))
          preds = set(
              row[0] for row in conn.execute("SELECT DISTINCT predicate FROM relations")
          )
          assert types == set(ENTITY_TYPES), set(ENTITY_TYPES) - types
          assert preds == set(PREDICATES), set(PREDICATES) - preds
          checks += 1

          # An edge naming an entity a later document defines still lands: the SOP
          # document names the Release Process, the deployments document defines it.
          row = conn.execute(
              "SELECT e1.name, r.predicate, e2.name FROM relations r "
              "JOIN entities e1 ON e1.id = r.source_id "
              "JOIN entities e2 ON e2.id = r.target_id "
              "WHERE r.predicate = 'governs' AND e2.name = 'Release Process'"
          ).fetchall()
          assert row == [
              ("No effort estimates in documents", "governs", "Release Process")
          ], row
          conn.close()
          checks += 1

          # Deterministic: a second build over the same input is byte-identical.
          again = Path(tmp) / "again.db"
          build(FIXTURE / "extraction", again)
          assert db.read_bytes() == again.read_bytes(), "build is not deterministic"
          checks += 1

    # One entity named in two documents is one node.
    assert entity_id("SYSTEM", "Checkout Service") == entity_id(
        "SYSTEM", "  checkout   SERVICE "
    )
    assert entity_id("SYSTEM", "Checkout Service") != entity_id("ROLE", "Checkout Service")
    checks += 1

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "extraction"
        src.mkdir()
        (src / "bad.json").write_text(
            json.dumps(
                {
                    "source_doc": "bad.md",
                    "nodes": [
                        {"name": "Thing", "type": "SYSTEM"},
                        {"name": "Ghost", "type": "WIDGET"},
                    ],
                    "edges": [
                        {"source": "Thing", "predicate": "part_of", "target": "Nowhere"},
                        {"source": "Thing", "predicate": "smells_like", "target": "Thing"},
                    ],
                    "aliases": [{"entity": "Nobody", "alias": "nb"}],
                }
            ),
            encoding="utf-8",
        )
        counts, problems = build(src, root / "g.db")
        assert counts["entities"] == 1, counts
        assert counts["relations"] == 0, counts
        assert len(problems) == 4, problems
        assert any("WIDGET" in p for p in problems), problems
        assert any("smells_like" in p for p in problems), problems
        assert any("skipped edge" in p for p in problems), problems
        assert any("skipped alias" in p for p in problems), problems
        checks += 1

        # A cross-document edge: `sops.md` names the process `deployments.md`
        # defines, and neither document is wrong. Pass two is what resolves it.
        pair = root / "pair"
        pair.mkdir()
        (pair / "governance__sops.json").write_text(
            json.dumps(
                {
                    "source_doc": "governance/sops.md",
                    "nodes": [{"name": "No estimates", "type": "SOP", "description": "MUST NOT"}],
                    "edges": [
                        {
                            "source": "No estimates",
                            "predicate": "governs",
                            "target": "Release Process",
                        }
                    ],
                    "aliases": [{"entity": "No estimates", "alias": "no-estimates"}],
                }
            ),
            encoding="utf-8",
        )
        (pair / "operational__deployments.json").write_text(
            json.dumps(
                {
                    "source_doc": "operational/deployments.md",
                    "nodes": [
                        {"name": "Release Process", "type": "PROCESS", "description": "Weekly"}
                    ],
                    "edges": [],
                    "aliases": [],
                }
            ),
            encoding="utf-8",
        )
        counts, problems = build(pair, root / "pair.db")
        assert problems == [], problems
        assert counts == {
            "entities": 2,
            "relations": 1,
            "aliases": 1,
            "documents": 2,
        }, counts
        checks += 1

        # Deterministic: a second build over the same input is byte-identical.
        build(pair, root / "pair-again.db")
        assert (root / "pair.db").read_bytes() == (
            root / "pair-again.db"
        ).read_bytes(), "build is not deterministic"
        checks += 1

        # An empty extraction directory is a valid, empty graph, not a crash.
        empty = root / "empty"
        empty.mkdir()
        counts, problems = build(empty, root / "e.db")
        assert counts["entities"] == 0 and problems == [], (counts, problems)
        checks += 1

    print("OK build_graph %d checks" % checks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
