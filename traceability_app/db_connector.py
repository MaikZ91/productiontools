"""DbConnector – Datenbankanbindung für das Rückverfolgbarkeits-Tool.

Standardmäßig wird eine lokale SQLite-Datenbank verwendet. Über die
Umgebungsvariable TRACE_DB_PATH kann der Speicherort geändert werden;
die Klasse kapselt alle Zugriffe, sodass später z. B. ein Wechsel auf
SQL Server / PostgreSQL nur hier stattfinden muss.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get(
    "TRACE_DB_PATH",
    os.path.join(os.path.dirname(__file__), "traceability.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_type   TEXT NOT NULL,
    serial_number TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE (device_type, serial_number)
);

CREATE TABLE IF NOT EXISTS components (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    sap_nr    TEXT,
    rev       TEXT,
    order_nr  TEXT,
    sn        TEXT,
    comp_date TEXT,
    UNIQUE (device_id, name)
);
"""


class DbConnector:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as c:
            c.executescript(SCHEMA)

    # ---- Schreiben -----------------------------------------------------
    def save_device(self, device_type, serial_number, components):
        """Legt ein Gerät an (oder aktualisiert es) und speichert seine
        Komponenten. `components` ist eine Liste von Dicts mit den Keys
        name, sap_nr, rev, order_nr, sn, comp_date."""
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO devices (device_type, serial_number, created_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(device_type, serial_number)
                   DO UPDATE SET created_at = created_at
                   RETURNING id""",
                (device_type, serial_number, datetime.now().isoformat(timespec="seconds")),
            )
            device_id = cur.fetchone()["id"]
            for comp in components:
                if not comp.get("name"):
                    continue
                c.execute(
                    """INSERT INTO components
                         (device_id, name, sap_nr, rev, order_nr, sn, comp_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(device_id, name) DO UPDATE SET
                         sap_nr=excluded.sap_nr, rev=excluded.rev,
                         order_nr=excluded.order_nr, sn=excluded.sn,
                         comp_date=excluded.comp_date""",
                    (
                        device_id,
                        comp["name"].strip(),
                        comp.get("sap_nr", "").strip(),
                        comp.get("rev", "").strip(),
                        comp.get("order_nr", "").strip(),
                        comp.get("sn", "").strip(),
                        comp.get("comp_date", "").strip(),
                    ),
                )
            return device_id

    # ---- Lesen ---------------------------------------------------------
    def fetch_devices(self, search=None):
        """Alle Geräte inkl. Komponenten, optional gefiltert nach
        Seriennummer / Typ / Komponenten-SN."""
        with self._conn() as c:
            if search:
                like = f"%{search}%"
                rows = c.execute(
                    """SELECT DISTINCT d.* FROM devices d
                       LEFT JOIN components k ON k.device_id = d.id
                       WHERE d.serial_number LIKE ? OR d.device_type LIKE ?
                          OR k.sn LIKE ? OR k.name LIKE ?
                       ORDER BY d.created_at DESC""",
                    (like, like, like, like),
                ).fetchall()
            else:
                rows = c.execute(
                    "SELECT * FROM devices ORDER BY created_at DESC"
                ).fetchall()
            devices = []
            for r in rows:
                comps = c.execute(
                    "SELECT * FROM components WHERE device_id = ? ORDER BY id",
                    (r["id"],),
                ).fetchall()
                devices.append({**dict(r), "components": [dict(x) for x in comps]})
            return devices

    def stats(self):
        with self._conn() as c:
            n_dev = c.execute("SELECT COUNT(*) n FROM devices").fetchone()["n"]
            n_comp = c.execute("SELECT COUNT(*) n FROM components").fetchone()["n"]
            n_types = c.execute(
                "SELECT COUNT(DISTINCT device_type) n FROM devices"
            ).fetchone()["n"]
            return {"devices": n_dev, "components": n_comp, "types": n_types}
