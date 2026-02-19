"""
Kore - Database layer
Handles SQLite connection and schema initialization.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"


def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Ensure DB file exists before chmod
    DB_PATH.touch(exist_ok=True)
    DB_PATH.chmod(0o600)  # owner only — protects memory data

    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id        TEXT    NOT NULL DEFAULT 'default',
                content         TEXT    NOT NULL,
                category        TEXT    NOT NULL DEFAULT 'general',
                importance      INTEGER NOT NULL DEFAULT 1 CHECK (importance BETWEEN 1 AND 5),
                decay_score     REAL    NOT NULL DEFAULT 1.0,
                access_count    INTEGER NOT NULL DEFAULT 0,
                last_accessed   TEXT    DEFAULT NULL,
                compressed_into INTEGER DEFAULT NULL REFERENCES memories(id),
                embedding       TEXT    DEFAULT NULL,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_memories_agent      ON memories (agent_id);
            CREATE INDEX IF NOT EXISTS idx_memories_decay      ON memories (decay_score DESC);
            CREATE INDEX IF NOT EXISTS idx_memories_compressed ON memories (compressed_into);

            CREATE INDEX IF NOT EXISTS idx_memories_category  ON memories (category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories (importance DESC);
            CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories (created_at DESC);

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
            USING fts5(content, category, content='memories', content_rowid='id', tokenize='unicode61');

            CREATE TRIGGER IF NOT EXISTS memories_ai
            AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts (rowid, content, category)
                VALUES (new.id, new.content, new.category);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad
            AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts (memories_fts, rowid, content, category)
                VALUES ('delete', old.id, old.content, old.category);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au
            AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts (memories_fts, rowid, content, category)
                VALUES ('delete', old.id, old.content, old.category);
                INSERT INTO memories_fts (rowid, content, category)
                VALUES (new.id, new.content, new.category);
            END;
        """)


@contextmanager
def get_connection():
    """Yield a thread-safe SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
