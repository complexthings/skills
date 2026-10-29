-- Copied from .claude/skills/rex-kb-update/scripts/schema.sql (ADR 0015).
-- The Rex knowledge graph. Three tables, no indexes beyond the primary key:
-- a project knowledge base is thousands of rows, not millions, and the walk
-- is a single recursive query over a table SQLite keeps in page cache.
--
-- `entities.id` is uuid5(NAMESPACE_OID, "<TYPE>:<normalised name>"), so the
-- same entity named in two documents is one node with no lookup and no model
-- call. The type and predicate vocabulary is closed: the extraction prompt
-- shipped alongside this schema states it in full.

CREATE TABLE entities  (id TEXT PRIMARY KEY,          -- uuid5(type + normalised name)
                        name TEXT NOT NULL,
                        type TEXT NOT NULL,           -- one of the closed vocabulary's eight
                        description TEXT NOT NULL DEFAULT '',
                        source_doc TEXT NOT NULL);

CREATE TABLE relations (source_id TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        predicate TEXT NOT NULL,      -- one of the closed vocabulary's eight
                        source_doc TEXT NOT NULL);

CREATE TABLE aliases   (entity_id TEXT NOT NULL,
                        alias TEXT NOT NULL);
