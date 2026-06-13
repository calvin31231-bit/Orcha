"""
init_db.py — SQLite database initialization for Mordu Market Engine.
Creates mordu.db with WAL mode and all required tables.
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "mordu.db"


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """Return a WAL-mode SQLite connection."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply performance and safety PRAGMAs."""
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA cache_size=-32000;
        PRAGMA foreign_keys=ON;
    """)


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all Mordu tables if they don't already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS market_orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            region_id       INTEGER NOT NULL,
            type_id         INTEGER NOT NULL,
            price           REAL    NOT NULL,
            volume_remain   INTEGER NOT NULL,
            is_buy_order    INTEGER NOT NULL,   -- 0 = sell, 1 = buy
            location_id     INTEGER NOT NULL,
            issued          TEXT    NOT NULL,
            expires         TEXT    NOT NULL,
            etag            TEXT,
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_orders_region_type
            ON market_orders (region_id, type_id);

        CREATE TABLE IF NOT EXISTS market_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            region_id   INTEGER NOT NULL,
            type_id     INTEGER NOT NULL,
            date        TEXT    NOT NULL,
            average     REAL    NOT NULL,
            highest     REAL    NOT NULL,
            lowest      REAL    NOT NULL,
            order_count INTEGER NOT NULL,
            volume      INTEGER NOT NULL,
            UNIQUE (region_id, type_id, date)
        );

        CREATE INDEX IF NOT EXISTS idx_history_region_type
            ON market_history (region_id, type_id);

        CREATE TABLE IF NOT EXISTS tracked_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id     INTEGER NOT NULL,
            type_name   TEXT    NOT NULL,
            region_id   INTEGER NOT NULL,
            active      INTEGER NOT NULL DEFAULT 1,
            UNIQUE (type_id, region_id)
        );

        CREATE TABLE IF NOT EXISTS character_skills (
            character_id            INTEGER PRIMARY KEY,
            accounting_level        INTEGER NOT NULL DEFAULT 0,
            broker_relations_level  INTEGER NOT NULL DEFAULT 0,
            updated_at              TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ai_briefs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type_id     INTEGER,
            region_id   INTEGER,
            brief_text  TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wallet_balance (
            character_id    INTEGER PRIMARY KEY,
            balance         REAL    NOT NULL,
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        -- OAuth2 refresh tokens (used by sso_auth.py)
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            character_id    INTEGER PRIMARY KEY,
            refresh_token   TEXT    NOT NULL,
            access_token    TEXT,
            expires_at      TEXT,
            character_name  TEXT,
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()


def init_db(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """
    Full initialization: open connection, apply PRAGMAs, create tables.
    Returns the open connection.
    """
    conn = get_connection(db_path)
    apply_pragmas(conn)
    create_tables(conn)
    return conn


if __name__ == "__main__":
    print(f"Initializing database at: {DB_PATH}")
    conn = init_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print("Tables created:")
    for row in tables:
        print(f"  {row['name']}")
    conn.close()
    print("Done.")
