"""
Kore - Database layer
Handles SQLite connection and schema initialization.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config


def _get_db_path() -> Path:
    """Risolve il path del DB a runtime (supporta override via KORE_DB_PATH)."""
    # Controlla env var a runtime per supporto test con DB temporaneo
    return Path(os.getenv("KORE_DB_PATH", config.DEFAULT_DB_PATH))


def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure DB file exists before chmod
    db_path.touch(exist_ok=True)
    db_path.chmod(0o600)  # owner only — protects memory data

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
                expires_at      TEXT    DEFAULT NULL,
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

            -- Tag per memorie
            CREATE TABLE IF NOT EXISTS memory_tags (
                memory_id   INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                tag         TEXT    NOT NULL,
                PRIMARY KEY (memory_id, tag)
            );
            CREATE INDEX IF NOT EXISTS idx_tags_tag ON memory_tags (tag);

            -- Relazioni tra memorie (grafo)
            CREATE TABLE IF NOT EXISTS memory_relations (
                source_id   INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                target_id   INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
                relation    TEXT    NOT NULL DEFAULT 'related',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (source_id, target_id, relation)
            );
            CREATE INDEX IF NOT EXISTS idx_relations_source ON memory_relations (source_id);
            CREATE INDEX IF NOT EXISTS idx_relations_target ON memory_relations (target_id);
        """)

        # Migrazione: aggiungi expires_at se mancante (DB pre-esistenti)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "expires_at" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN expires_at TEXT DEFAULT NULL")


@contextmanager
def get_connection():
    """Yield a thread-safe SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
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
