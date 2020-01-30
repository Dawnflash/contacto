CREATE TABLE IF NOT EXISTS "group" (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS entity (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    thumbnail BLOB,
    group_id INTEGER NOT NULL REFERENCES "group"(id) ON DELETE CASCADE,
    UNIQUE(group_id, name)
);
CREATE TABLE IF NOT EXISTS attribute (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    type INTEGER NOT NULL,
    data BLOB NOT NULL,
    entity_id INTEGER NOT NULL REFERENCES entity(id) ON DELETE CASCADE,
    UNIQUE(entity_id, name)
);
