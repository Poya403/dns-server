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
        domain TEXT NOT NULL,
        qtype TEXT NOT NULL,
        value TEXT NOT NULL,
        ttl INTEGER,
        prorarity INTEGER,
        PRIMARY KEY (domain, qtype, value)
    );
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
        INSERT INTO records(domain, qtype, value, ttl, prorarity)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(domain, qtype, value) DO UPDATE SET
            ttl = excluded.ttl,
            prorarity = excluded.prorarity
    """, (record.domain, record.qtype, record.value, record.ttl, record.prorarity))
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

def get_records(domain: str = None, qtype: str = None):
    conn, cursor = get_connection()
    
    if domain and qtype:
        cursor.execute(
            "SELECT domain, qtype, value, ttl, prorarity FROM records WHERE domain=? AND qtype=?",
            (domain, qtype)
        )
    elif domain:
        cursor.execute(
            "SELECT domain, qtype, value, ttl, prorarity FROM records WHERE domain=?",
            (domain,)
        )
    elif qtype:
        cursor.execute(
            "SELECT domain, qtype, value, ttl, prorarity FROM records WHERE qtype=?",
            (qtype,)
        )
    else:
        cursor.execute(
            "SELECT domain, qtype, value, ttl, prorarity FROM records"
        )
    
    rows = cursor.fetchall()
    conn.close()
    return [{"domain": r[0], "qtype": r[1], "value": r[2], "ttl": r[3], "prorarity": r[4]} for r in rows]

def get_logs(domain: str = None, qtype: str = None):
    conn, cursor = get_connection()
    cursor.execute("SELECT domain, qtype, user_ip, src, created_at FROM logs ORDER BY id DESC LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    return [{"domain": r[0], "qtype": r[1], "user_ip": r[2], "src": r[3], "created_at" : r[4]} for r in rows]