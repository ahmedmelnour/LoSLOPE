"""SQLite persistence layer for LoSLOPE.

Two tables:
  - nodes    : field node metadata + GPS location (user managed via the UI)
  - readings : the sensor time-series, one row per ingested LoRa packet
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


# A single shared connection is fine for SQLite with WAL + a serialization lock.
_conn = _connect()


@contextmanager
def get_db():
    """Yield the shared connection, committing on success."""
    try:
        yield _conn
        _conn.commit()
    except Exception:
        _conn.rollback()
        raise


def init_db() -> None:
    """Create tables and indexes if they do not exist."""
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id           INTEGER PRIMARY KEY,
                name         TEXT NOT NULL,
                latitude     REAL,
                longitude    REAL,
                install_date TEXT,
                notes        TEXT
            );

            CREATE TABLE IF NOT EXISTS readings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id    INTEGER NOT NULL,
                seq        INTEGER,
                ts         TEXT NOT NULL,          -- server timestamp (ISO 8601, UTC)
                tilt_dev   REAL,
                tilt_rate  REAL,
                soil       REAL,
                soil_rate  REAL,
                vib        INTEGER,
                ttc        REAL,
                lvl        INTEGER,
                rssi       REAL,
                -- ML enrichment, filled in by the pipeline at ingest time
                anomaly    REAL,
                risk       REAL
            );

            CREATE INDEX IF NOT EXISTS idx_readings_node_ts
                ON readings (node_id, ts);
            """
        )


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Node CRUD -------------------------------------------------------------

def list_nodes() -> list[dict]:
    with get_db() as db:
        rows = db.execute("SELECT * FROM nodes ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_node(node_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return dict(row) if row else None


def create_node(node: dict) -> dict:
    with get_db() as db:
        db.execute(
            """INSERT INTO nodes (id, name, latitude, longitude, install_date, notes)
               VALUES (:id, :name, :latitude, :longitude, :install_date, :notes)""",
            node,
        )
    return get_node(node["id"])


def update_node(node_id: int, fields: dict) -> dict | None:
    if not fields:
        return get_node(node_id)
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    params = {**fields, "id": node_id}
    with get_db() as db:
        db.execute(f"UPDATE nodes SET {sets} WHERE id = :id", params)
    return get_node(node_id)


def delete_node(node_id: int) -> None:
    with get_db() as db:
        db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))


# --- Readings --------------------------------------------------------------

def insert_reading(r: dict) -> int:
    with get_db() as db:
        cur = db.execute(
            """INSERT INTO readings
               (node_id, seq, ts, tilt_dev, tilt_rate, soil, soil_rate,
                vib, ttc, lvl, rssi, anomaly, risk)
               VALUES
               (:node_id, :seq, :ts, :tilt_dev, :tilt_rate, :soil, :soil_rate,
                :vib, :ttc, :lvl, :rssi, :anomaly, :risk)""",
            r,
        )
        return cur.lastrowid


def get_readings(node_id: int | None, frm: str | None, to: str | None,
                 limit: int = 5000) -> list[dict]:
    clauses, params = [], []
    if node_id is not None:
        clauses.append("node_id = ?")
        params.append(node_id)
    if frm:
        clauses.append("ts >= ?")
        params.append(frm)
    if to:
        clauses.append("ts <= ?")
        params.append(to)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM readings {where} ORDER BY ts ASC LIMIT ?", params
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_readings(node_id: int, limit: int) -> list[dict]:
    """Most recent `limit` readings for a node, returned oldest-first."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM readings WHERE node_id = ? ORDER BY ts DESC LIMIT ?",
            (node_id, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def latest_reading(node_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM readings WHERE node_id = ? ORDER BY ts DESC LIMIT 1",
            (node_id,),
        ).fetchone()
    return dict(row) if row else None


def all_readings_for_training(limit: int = 50000) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM readings ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def alert_log(limit: int = 200) -> list[dict]:
    """WARNING (2) and CRITICAL (3) events, newest first."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM readings WHERE lvl >= 2 ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
