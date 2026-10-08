"""SQLite 연결과 스키마."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS shippers (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  contact TEXT
);
CREATE TABLE IF NOT EXISTS vehicles (
  id INTEGER PRIMARY KEY,
  plate TEXT NOT NULL UNIQUE,
  vehicle_type TEXT NOT NULL,
  capacity_ton REAL NOT NULL,
  driver_name TEXT,
  driver_phone TEXT,
  status TEXT NOT NULL DEFAULT 'IDLE',
  lat REAL, lng REAL,
  home_label TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY,
  order_no TEXT NOT NULL UNIQUE,
  shipper_id INTEGER REFERENCES shippers(id),
  origin_name TEXT, origin_addr TEXT, origin_lat REAL, origin_lng REAL,
  dest_name TEXT, dest_addr TEXT, dest_lat REAL, dest_lng REAL,
  pickup_at TEXT, due_at TEXT,
  vehicle_type TEXT NOT NULL,
  weight_ton REAL NOT NULL,
  cargo_desc TEXT,
  status TEXT NOT NULL DEFAULT 'REQUESTED',
  vehicle_id INTEGER REFERENCES vehicles(id),
  distance_km REAL, duration_min REAL,
  route_source TEXT, route_path TEXT,
  fare_krw INTEGER,
  empty_km REAL,
  progress REAL DEFAULT 0,
  eta TEXT,
  created_at TEXT, assigned_at TEXT, loaded_at TEXT, departed_at TEXT, delivered_at TEXT
);
CREATE TABLE IF NOT EXISTS order_events (
  id INTEGER PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id),
  from_status TEXT, to_status TEXT NOT NULL,
  note TEXT,
  at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vehicle_positions (
  id INTEGER PRIMARY KEY,
  vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
  order_id INTEGER,
  lat REAL, lng REAL, speed_kmh REAL,
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_positions_vehicle ON vehicle_positions(vehicle_id, at);
"""


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: Path | None = None) -> None:
    with _connect(path or config.DB_PATH) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn(path: Path | None = None):
    conn = _connect(path or config.DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def one(cur) -> dict | None:
    r = cur.fetchone()
    return dict(r) if r else None
