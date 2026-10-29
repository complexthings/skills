#!/usr/bin/env python3
# Copied from .claude/skills/rex-kb-update/scripts/recall.py (ADR 0015).
"""Walk the Rex knowledge graph: seed from the prompt, follow k hops, return facts.

**No model call anywhere in this file.** It runs inside a hook, on every prompt,
before the model is invoked, so it has to be deterministic and fast. One
recursive SQL query does the whole traversal; the model does no retrieval.

Seeding is literal: an entity is a seed when its name or one of its aliases
appears as a whole word in the prompt. That is deliberately dumb -- a fuzzy match
would put a judgement call in the one place that must not make one.

**The budget.** Hook `additionalContext` is capped at 10 KB across every hook that
returns one, joined with a double newline, so this walk claims 8000 bytes and
leaves the rest for whatever else a repository has installed. What survives the
cap is chosen, not whatever sorted first:

1. Triples come back ordered by `near` -- the hop distance of the nearer endpoint
   -- so the facts closest to what the prompt actually named survive first, and
   ties break on the entity and predicate names so the order is stable.
2. `--top-k` caps the count before the byte budget is applied at all.
3. Triples are emitted until the next one would cross the budget, then dropped.
4. Descriptions ("where:") are appended only from what is left, one entity at a
   time, and dropped whole rather than truncated mid-sentence.

A prompt that names nothing in the graph gets "no memory matches for this
prompt". That is the correct answer to a question outside the vocabulary; a guess
is not.

Standard library only, Python 3.9 floor (ADR-0012, ADR-0025).
"""
import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_DB = Path(".agents") / "project-knowledge" / "graph" / "graph.db"

# Hooks share a 10 KB additionalContext cap; claim 8 KB and leave headroom.
BUDGET_BYTES = 8000
DEFAULT_HOPS = 3
DEFAULT_TOP_K = 10

NO_MATCH = "(no memory matches for this prompt)"

WALK = """
WITH RECURSIVE walk(entity_id, depth) AS (
  SELECT id, 0 FROM entities WHERE id IN ({seeds})
  UNION
  SELECT CASE WHEN r.source_id = w.entity_id
              THEN r.target_id ELSE r.source_id END,
         w.depth + 1
  FROM relations r JOIN walk w
    ON w.entity_id IN (r.source_id, r.target_id)
  WHERE w.depth < ?
)
SELECT e1.name, r.predicate, e2.name, r.source_doc,
       MIN((SELECT MIN(depth) FROM walk WHERE entity_id = r.source_id),
           (SELECT MIN(depth) FROM walk WHERE entity_id = r.target_id)) AS near
FROM relations r
JOIN entities e1 ON e1.id = r.source_id
JOIN entities e2 ON e2.id = r.target_id
WHERE r.source_id IN (SELECT entity_id FROM walk)
  AND r.target_id IN (SELECT entity_id FROM walk)
GROUP BY e1.name, r.predicate, e2.name, r.source_doc
ORDER BY near, e1.name, r.predicate, e2.name, r.source_doc
"""


class Facts(object):
    """Triples, the descriptions of the entities in them, and how long it took."""

    def __init__(self, triples, notes, ms):
        self.triples = triples  # (source, predicate, target, source_doc)
        self.notes = notes  # (entity_name, description)
        self.ms = ms

    def as_text(self, budget=BUDGET_BYTES):
        """Render within `budget` bytes, dropping the furthest facts first."""
        header = "rex memory: %d fact(s) recalled in %.0f ms" % (
            len(self.triples),
            self.ms,
        )
        if not self.triples:
            return header + "\n" + NO_MATCH

        lines = []
        used = len(header.encode("utf-8")) + 2
        kept = set()
        for source, predicate, target, doc in self.triples:
            line = "%s --[%s]--> %s   (%s)" % (source, predicate, target, doc)
            cost = len(line.encode("utf-8")) + 1
            if used + cost > budget:
                break
            lines.append(line)
            used += cost
            kept.add(source)
            kept.add(target)

        if not lines:
            # Even one triple did not fit. Say so rather than returning a header
            # that claims facts the reader cannot see.
            return header + "\n" + NO_MATCH

        text = header + "\n\n" + "\n".join(lines)
        # Conditions -- targets, baselines, rule strength -- live on the
        # entities, not the edges. Carry as many as the budget still allows.
        notes = []
        used = len(text.encode("utf-8"))
        for name, description in self.notes:
            if name not in kept:
                continue
            note = "  %s: %s" % (name, description)
            cost = len(note.encode("utf-8")) + 1
            if used + len("\n\nwhere:".encode("utf-8")) + cost > budget:
                break
            notes.append(note)
            used += cost
        if notes:
            text += "\n\nwhere:\n" + "\n".join(notes)
        return text


def seeds(db, question):
    """Ids of entities whose name or alias appears as a whole word in `question`."""
    lowered = question.lower()
    found = []
    seen = set()
    rows = list(db.execute("SELECT id, name FROM entities ORDER BY name"))
    rows += list(db.execute("SELECT entity_id, alias FROM aliases ORDER BY alias"))
    for eid, text in rows:
        if eid in seen:
            continue
        if re.search(r"\b%s\b" % re.escape(text.lower()), lowered):
            seen.add(eid)
            found.append(eid)
    return found


def recall(question, db_path=DEFAULT_DB, hops=DEFAULT_HOPS, top_k=DEFAULT_TOP_K):
    started = time.time()
    db_path = Path(db_path)
    if not db_path.is_file():
        return Facts([], [], (time.time() - started) * 1000)
    db = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        found = seeds(db, question)
        if not found:
            return Facts([], [], (time.time() - started) * 1000)
        marks = ",".join("?" * len(found))
        params = tuple(found) + (hops,)
        rows = db.execute(WALK.format(seeds=marks), params).fetchall()
        triples = [(s, p, t, doc) for s, p, t, doc, _ in rows[:top_k]]
        names = sorted(set(n for s, _, t, _ in triples for n in (s, t)))
        notes = []
        if names:
            marks = ",".join("?" * len(names))
            notes = list(
                db.execute(
                    "SELECT name, description FROM entities "
                    "WHERE name IN (%s) AND description != '' ORDER BY name" % marks,
                    tuple(names),
                )
            )
        return Facts(triples, notes, (time.time() - started) * 1000)
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("question", nargs="*", help="the prompt to seed the walk from")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="graph database to read")
    parser.add_argument("--hops", type=int, default=DEFAULT_HOPS)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--budget", type=int, default=BUDGET_BYTES)
    parser.add_argument("--selftest", action="store_true", help="run the selftest and exit")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    question = " ".join(args.question)
    if not question:
        print("nothing to recall: pass a question", file=sys.stderr)
        return 2
    facts = recall(question, args.db, args.hops, args.top_k)
    print(facts.as_text(args.budget))
    return 0


# --- selftest ----------------------------------------------------------------

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "rex-graph"

# The same three-hop chain the committed fixture has, small enough to write into
# a temp directory. A bundled copy of this script sits inside an installed skill
# with no `.agents/fixtures/` above it, and a `--selftest` that silently tested
# nothing there would be worse than having none at all. When the fixture *is*
# next door it is tested too -- the two are not substitutes.
CORPUS = [
    {
        "source_doc": "technical/stack.md",
        "nodes": [
            {"name": "Checkout Service", "type": "SYSTEM", "description": "Owns the basket"},
            {"name": "Payment Gateway", "type": "SYSTEM", "description": "The payment provider"},
        ],
        "edges": [
            {"source": "Checkout Service", "predicate": "depends_on", "target": "Payment Gateway"}
        ],
        "aliases": [{"entity": "Payment Gateway", "alias": "PSP"}],
    },
    {
        "source_doc": "governance/kpis.md",
        "nodes": [
            {
                "name": "Checkout Conversion Rate",
                "type": "KPI",
                "description": "target 3.4%, baseline 2.6% in Q2",
            }
        ],
        "edges": [
            {
                "source": "Checkout Service",
                "predicate": "supports",
                "target": "Checkout Conversion Rate",
            }
        ],
        "aliases": [],
    },
    {
        "source_doc": "people/roles.md",
        "nodes": [
            {
                "name": "Head of Ecommerce",
                "type": "ROLE",
                "description": "Accountable for the conversion number",
            }
        ],
        "edges": [
            {
                "source": "Checkout Conversion Rate",
                "predicate": "owned_by",
                "target": "Head of Ecommerce",
            }
        ],
        "aliases": [],
    },
    {
        "source_doc": "operational/deployments.md",
        "nodes": [
            {"name": "Release Process", "type": "PROCESS", "description": "Weekly Thursday train"}
        ],
        "edges": [
            {"source": "Checkout Service", "predicate": "depends_on", "target": "Release Process"}
        ],
        "aliases": [],
    },
]


def write_corpus(directory):
    """Write `CORPUS` as extraction JSON. Returns the directory."""
    import json

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for doc in CORPUS:
        name = doc["source_doc"][: -len(".md")].replace("/", "__") + ".json"
        (directory / name).write_text(json.dumps(doc), encoding="utf-8")
    return directory


def _selftest():
    """Walk a real graph. The chained question is the point.

    Runs against the committed fixture when it is reachable, and against the
    inline corpus always, so a bundled copy still proves the walk works.
    """
    import tempfile

    from build_graph import build  # noqa: E402  same directory, bundled together

    checks = 0

    def drive(extraction, label):
        """Every assertion, against whichever corpus. Returns the check count."""
        run = 0
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "graph.db"
            _, problems = build(extraction, db)
            assert problems == [], (label, problems)

            # Three hops. Nothing states that the payment gateway has anything to
            # do with the Head of Ecommerce; the walk crosses four documents to
            # get there. This is what fails if the walk regresses to one hop.
            question = "we are changing how the Payment Gateway is called"
            facts = recall(question, db, hops=3, top_k=20)
            chained = ("Checkout Conversion Rate", "owned_by", "Head of Ecommerce")
            assert chained in [(s, p, t) for s, p, t, _ in facts.triples], (label, facts.triples)
            docs = set(doc for _, _, _, doc in facts.triples)
            assert len(docs) >= 4, (label, docs)
            run += 1

            # ...and it is genuinely three hops away, not something one hop reaches.
            one_hop = recall(question, db, hops=1, top_k=20)
            assert chained not in [(s, p, t) for s, p, t, _ in one_hop.triples], (
                "%s: a one-hop walk reached a three-hop fact -- the corpus no "
                "longer proves multi-hop recall" % label
            )
            assert one_hop.triples, (label, "one hop should still reach the seed's own edge")
            run += 1

            # An alias seeds the same walk as the name it stands for.
            by_alias = recall("what does PSP touch?", db, hops=3, top_k=20)
            assert chained in [(s, p, t) for s, p, t, _ in by_alias.triples], (
                label,
                by_alias.triples,
            )
            run += 1

            # A question outside the vocabulary gets a legible nothing, not a guess.
            nothing = recall("how do I rotate the tyres on a forklift?", db)
            assert nothing.triples == [], (label, nothing.triples)
            assert NO_MATCH in nothing.as_text()
            run += 1

            # The budget is respected, and respecting it drops the furthest facts.
            full = facts.as_text()
            assert len(full.encode("utf-8")) <= BUDGET_BYTES, (label, len(full))
            run += 1

            first = facts.triples[0]
            last = facts.triples[-1]
            assert first != last, (label, "the budget test needs more than one triple")
            # Exactly enough room for the header and the nearest triple, so the
            # furthest triple and the descriptions both have to be dropped.
            header = facts.as_text().split("\n\n")[0]
            line = "%s --[%s]--> %s   (%s)" % first
            budget = (
                len(header.encode("utf-8"))
                + 2
                + len(line.encode("utf-8"))
                + 1
            )
            tight = facts.as_text(budget=budget)
            assert len(tight.encode("utf-8")) <= budget, (label, tight)
            assert "where:" not in tight, (label, tight)
            assert "%s --[%s]--> %s" % first[:3] in tight, (label, tight)
            assert "%s --[%s]--> %s" % last[:3] not in tight, (label, tight)
            run += 1

            # Descriptions carry the conditions the edges cannot.
            assert "target 3.4%" in full, (label, full)
            run += 1

            # A budget too small for even one triple says nothing, not a lie.
            assert facts.as_text(budget=10).endswith(NO_MATCH)
            run += 1

            # A missing database is a quiet nothing, not a traceback: recall runs
            # on every prompt, including where the graph was never built.
            assert recall("Payment Gateway", Path(tmp) / "absent.db").triples == []
            run += 1
        return run

    with tempfile.TemporaryDirectory() as tmp:
        checks += drive(write_corpus(Path(tmp) / "extraction"), "inline")
    if FIXTURE.is_dir():
        checks += drive(FIXTURE / "extraction", "fixture")

    print("OK recall %d checks" % checks)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
