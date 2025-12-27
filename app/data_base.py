import sqlite3
from typing import List, Tuple

DB_FILE = "db/records.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            qtype TEXT NOT NULL,
            value TEXT NOT NULL,
            ttl INTEGER DEFAULT 60,
            UNIQUE(domain, qtype, value)
        )
        """)
        self.conn.commit()

    def get_records(self, domain: str, qtype: str) -> List[Tuple[str, int]]:
        self.cursor.execute(
            "SELECT value, ttl FROM records WHERE domain=? AND qtype=?",
            (domain.lower(), qtype.upper())
        )
        return self.cursor.fetchall()

    def insert_record(self, domain: str, qtype: str, value: str, ttl: int):
        self.cursor.execute("""
            INSERT INTO records(domain, qtype, value, ttl)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(domain, qtype, value) DO UPDATE SET ttl=excluded.ttl
        """, (domain.lower(), qtype.upper(), value, ttl))
        self.conn.commit()
