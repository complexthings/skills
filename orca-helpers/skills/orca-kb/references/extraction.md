# Extraction format

Read this before an `update`. The extraction is the JSON that `--extraction` takes. Recall finds a fact only through the nodes, edges and aliases written here.

```json
{
  "nodes": [{"name": "Wave Band", "type": "SYSTEM", "description": "Draws each Work Item's progress"}],
  "edges": [{"source": "Wave Band", "predicate": "depends_on", "target": "Status File"}],
  "aliases": [{"entity": "Wave Band", "alias": "band"}]
}
```

- Node types: `CONCEPT`, `DOCUMENT`, `KPI`, `PERSON`, `PROCESS`, `ROLE`, `SOP`, `SYSTEM`.
- Predicates: `depends_on`, `governs`, `held_by`, `measured_by`, `owned_by`, `part_of`, `references`, `supports`.
- Put the lesson itself in the node's `description`. Recall prints it under `where:`.
- An edge's `source` and `target` name nodes in this extraction or in an earlier one.
- Give every node the aliases a future task uses for it: short names, file names, command names. Recall seeds only on a whole-word name or alias, so a node with no alias is a fact recall never finds. `lint` reports every non-`CONCEPT` node without one.
- The script refuses a write with no aliases or no edges, and a type or predicate outside the lists above.
