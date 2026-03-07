import sqlite3
from .config import DB_FILE

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS servers (
            id        INTEGER PRIMARY KEY,
            sub_url   TEXT,
            protocol  TEXT,
            transport TEXT DEFAULT 'tcp',
            host      TEXT,
            port      INTEGER,
            remark    TEXT,
            raw_uri   TEXT,
            uri_key   TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS pings (
            id         INTEGER PRIMARY KEY,
            server_id  INTEGER REFERENCES servers(id),
            ts         TEXT DEFAULT (datetime('now','localtime')),
            method     TEXT,
            latency_ms REAL,
            error      TEXT
        );
        CREATE TABLE IF NOT EXISTS speed_tests (
            id         INTEGER PRIMARY KEY,
            server_id  INTEGER REFERENCES servers(id),
            ts         TEXT DEFAULT (datetime('now','localtime')),
            size_bytes INTEGER,
            duration_s REAL,
            speed_mbps REAL,
            error      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pings_ts
            ON pings(server_id, ts);
        CREATE INDEX IF NOT EXISTS idx_speed_ts
            ON speed_tests(server_id, ts);
    """)
    return conn
