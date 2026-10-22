# -*- coding: utf-8 -*-
"""
Quan ly ket noi SQLite + schema. CHI lo ket noi/schema (Single Responsibility);
truy van nghiep vu nam o cac repository.
"""
import os
import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        new = not os.path.exists(self.path)
        self._local = threading.local()
        self._init_schema()
        if new:
            try:
                os.chmod(self.path, 0o600)   # file chua bi mat
            except OSError:
                pass

    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = c
        return c

    def _init_schema(self):
        with self.conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS whitelist(
                entry TEXT PRIMARY KEY,
                is_cidr INTEGER DEFAULT 0,
                source TEXT DEFAULT 'owner',
                note TEXT DEFAULT '',
                added_at INTEGER);
            CREATE TABLE IF NOT EXISTS sessions(
                token TEXT PRIMARY KEY, username TEXT, expiry INTEGER);
            CREATE TABLE IF NOT EXISTS samples(
                minute INTEGER PRIMARY KEY,
                requests INTEGER DEFAULT 0,
                errors404 INTEGER DEFAULT 0,
                scanners INTEGER DEFAULT 0,
                ssh_failed INTEGER DEFAULT 0,
                bans INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER, type TEXT, ip TEXT, jail TEXT, reason TEXT, detail TEXT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            """)
