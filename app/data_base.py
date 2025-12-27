import sqlite3
import os
from app.models import DNSRecordModel

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "db", "records.db")

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    return conn, cursor

def init_db():
    conn, cursor = get_connection()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        qtype TEXT NOT NULL,
        value TEXT NOT NULL,
        ttl INTEGER DEFAULT 60,
        priority INTEGER,
        UNIQUE(domain, qtype, value)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        qtype TEXT,
        user_ip TEXT,
        src TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS blacklist (
        domain TEXT PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()

def add_record(record: DNSRecordModel):
    conn, cursor = get_connection()
    cursor.execute("""
        INSERT INTO records(domain, qtype, value, ttl, priority)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(domain, qtype, value) DO UPDATE SET
            ttl = excluded.ttl,
            priority = excluded.priority
    """, (record.domain, record.qtype, record.value, record.ttl, record.priority))
    conn.commit()
    conn.close()

def delete_record(domain: str, qtype: str = None):
    conn, cursor = get_connection()
    if qtype:
        cursor.execute("DELETE FROM records WHERE domain=? AND qtype=?", (domain, qtype))
    else:
        cursor.execute("DELETE FROM records WHERE domain=?", (domain,))
    conn.commit()
    conn.close()

def get_records(domain: str, qtype: str = None):
    conn, cursor = get_connection()
    if qtype:
        cursor.execute("SELECT domain, qtype, value, ttl, priority FROM records WHERE domain=? AND qtype=?", (domain, qtype))
    else:
        cursor.execute("SELECT domain, qtype, value, ttl, priority FROM records WHERE domain=?", (domain,))
    rows = cursor.fetchall()
    conn.close()
    return [{"name": r[0], "type": r[1], "value": r[2], "ttl": r[3], "priority": r[4]} for r in rows]
