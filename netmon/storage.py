"""Histórico em disco (SQLite).

Tabelas:
  ping_minute  - médias por minuto de cada alvo de ping
  http_sample  - cada checagem HTTP (1 por minuto por serviço)
  ssh_sample   - cada coleta de CPU/RAM da ONT
  incident     - quedas e instabilidades detectadas
  heartbeat    - último instante em que o monitor estava rodando
"""
import sqlite3
import threading
import time

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS ping_minute (
    ts INTEGER NOT NULL, target TEXT NOT NULL,
    lat_avg REAL, lat_max REAL, loss_avg REAL NOT NULL, samples INTEGER NOT NULL,
    PRIMARY KEY (ts, target)
);
CREATE TABLE IF NOT EXISTS http_sample (
    ts INTEGER NOT NULL, service TEXT NOT NULL,
    ms REAL, ok INTEGER NOT NULL, detail TEXT,
    PRIMARY KEY (ts, service)
);
CREATE TABLE IF NOT EXISTS ssh_sample (
    ts INTEGER PRIMARY KEY, cpu REAL, ram REAL
);
CREATE TABLE IF NOT EXISTS incident (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL, target TEXT NOT NULL,
    start_ts INTEGER NOT NULL, end_ts INTEGER, detail TEXT
);
CREATE INDEX IF NOT EXISTS ix_incident_start ON incident (start_ts);
CREATE TABLE IF NOT EXISTS heartbeat (
    id INTEGER PRIMARY KEY CHECK (id = 1), ts INTEGER NOT NULL
);
"""


class Storage:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    def _write(self, sql, params=(), many=False):
        with self._lock:
            cur = self._conn.executemany(sql, params) if many else self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def _read_df(self, sql, params=()):
        with self._lock:
            return pd.read_sql_query(sql, self._conn, params=params)

    # --- escrita ---------------------------------------------------------
    def add_ping_minutes(self, rows):
        """rows: [(ts, target, lat_avg, lat_max, loss_avg, samples)]"""
        self._write("INSERT OR REPLACE INTO ping_minute VALUES (?,?,?,?,?,?)", rows, many=True)

    def add_http_samples(self, rows):
        """rows: [(ts, service, ms, ok, detail)]"""
        self._write("INSERT OR REPLACE INTO http_sample VALUES (?,?,?,?,?)", rows, many=True)

    def add_ssh_sample(self, ts, cpu, ram):
        self._write("INSERT OR REPLACE INTO ssh_sample VALUES (?,?,?)", (ts, cpu, ram))

    def open_incident(self, kind, target, start_ts, detail=""):
        return self._write(
            "INSERT INTO incident (kind, target, start_ts, end_ts, detail) VALUES (?,?,?,NULL,?)",
            (kind, target, start_ts, detail),
        )

    def close_incident(self, incident_id, end_ts):
        self._write("UPDATE incident SET end_ts = ? WHERE id = ?", (end_ts, incident_id))

    def add_closed_incident(self, kind, target, start_ts, end_ts, detail=""):
        self._write(
            "INSERT INTO incident (kind, target, start_ts, end_ts, detail) VALUES (?,?,?,?,?)",
            (kind, target, start_ts, end_ts, detail),
        )

    def close_dangling_incidents(self, end_ts):
        """Fecha incidentes que ficaram abertos porque o monitor foi encerrado."""
        self._write(
            "UPDATE incident SET end_ts = MAX(start_ts, ?), "
            "detail = COALESCE(detail, '') || ' (encerrado junto com o monitor)' "
            "WHERE end_ts IS NULL",
            (end_ts,),
        )

    def beat(self, ts):
        self._write("INSERT OR REPLACE INTO heartbeat (id, ts) VALUES (1, ?)", (ts,))

    def last_beat(self):
        with self._lock:
            row = self._conn.execute("SELECT ts FROM heartbeat WHERE id = 1").fetchone()
        return row[0] if row else None

    def prune(self, retention_days):
        cutoff = int(time.time()) - retention_days * 86400
        with self._lock:
            for table, col in (("ping_minute", "ts"), ("http_sample", "ts"),
                               ("ssh_sample", "ts"), ("incident", "start_ts")):
                self._conn.execute(f"DELETE FROM {table} WHERE {col} < ?", (cutoff,))
            self._conn.commit()

    # --- leitura ---------------------------------------------------------
    def ping_minutes(self, since_ts):
        return self._read_df("SELECT * FROM ping_minute WHERE ts >= ? ORDER BY ts", (since_ts,))

    def http_samples(self, since_ts):
        return self._read_df("SELECT * FROM http_sample WHERE ts >= ? ORDER BY ts", (since_ts,))

    def incidents(self, since_ts):
        # Inclui incidentes que começaram antes do período mas ainda o atravessam
        return self._read_df(
            "SELECT * FROM incident WHERE COALESCE(end_ts, strftime('%s','now')) >= ? "
            "ORDER BY start_ts DESC",
            (since_ts,),
        )

    def first_ts(self):
        with self._lock:
            row = self._conn.execute("SELECT MIN(ts) FROM ping_minute").fetchone()
        return row[0] if row and row[0] else None
