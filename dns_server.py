import socket
import sqlite3
import time
from dnslib import DNSRecord, RR, QTYPE, RCODE, A, NS, MX, CNAME

DNS_PORT = 53
UPSTREAM_DNS = ("8.8.8.8", 53)
DB_FILE = "dns.db"
DEFAULT_TTL = 60

cache = {}  # key = (domain, qtype_num) -> list of (value, expire_time)

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    qtype TEXT NOT NULL,
    value TEXT NOT NULL,
    ttl INTEGER DEFAULT 60,
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

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", DNS_PORT))

rdata_map = {
    "A": A,
    "NS": NS,
    "MX": MX,
    "CNAME": CNAME
}

def ask_upstream(domain, qtype="A"):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)
    try:
        q = DNSRecord.question(domain, qtype)
        sock.sendto(q.pack(), UPSTREAM_DNS)
        r = DNSRecord.parse(sock.recvfrom(512)[0])
        return r
    except:
        return None
    finally:
        sock.close()

print(f"DNS Server running on port {DNS_PORT} ...")

while True:
    data, addr = sock.recvfrom(512)
    req = DNSRecord.parse(data)
    rep = req.reply()

    domain = str(req.q.qname).rstrip(".").lower()
    qtype_num = req.q.qtype
    qtype_str = QTYPE[qtype_num]

    print(f"{addr[0]} -> {domain} ({qtype_str})")

    cursor.execute("SELECT 1 FROM blacklist WHERE domain=?", (domain,))
    if cursor.fetchone():
        rep.header.rcode = RCODE.NXDOMAIN
        sock.sendto(rep.pack(), addr)
        continue

    key = (domain, qtype_num)

    cached_list = cache.get(key, [])
    valid_rrs = []
    for val, expire in cached_list:
        if time.time() < expire:
            valid_rrs.append((val, expire))
            rdata_cls = rdata_map.get(qtype_str)
            if rdata_cls:
                rep.add_answer(RR(domain, qtype_num, rdata=rdata_cls(val), ttl=DEFAULT_TTL))
    if valid_rrs:
        cache[key] = valid_rrs
        cursor.execute(
            "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
            (domain, qtype_str, addr[0], "cache")
        )
        conn.commit()
        sock.sendto(rep.pack(), addr)
        continue
    else:
        cache.pop(key, None)

    cursor.execute("SELECT value, ttl FROM records WHERE domain=? AND qtype=?", (domain, qtype_str))
    rows = cursor.fetchall()
    if rows:
        valid_rrs = []
        for value, ttl in rows:
            ttl = ttl or DEFAULT_TTL
            valid_rrs.append((value, time.time() + ttl))
            rdata_cls = rdata_map.get(qtype_str)
            if rdata_cls:
                rep.add_answer(RR(domain, qtype_num, rdata=rdata_cls(value), ttl=ttl))
        cache[key] = valid_rrs
        cursor.execute(
            "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
            (domain, qtype_str, addr[0], "database")
        )
        conn.commit()
        sock.sendto(rep.pack(), addr)
        continue

    response = ask_upstream(domain, qtype_str)
    if response:
        cache_list = []
        for rr in response.rr:
            rr_qtype = rr.rtype
            rr_str_type = QTYPE[rr_qtype]
            val = str(rr.rdata)
            ttl = rr.ttl or DEFAULT_TTL

            k = (str(rr.rname).rstrip("."), rr_qtype)
            cache.setdefault(k, []).append((val, time.time() + ttl))

            cursor.execute("""
                INSERT INTO records(domain, qtype, value, ttl)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain, qtype, value) DO UPDATE SET
                    ttl = excluded.ttl
            """, (str(rr.rname).rstrip("."), rr_str_type, val, ttl))

            cursor.execute(
                "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
                (str(rr.rname).rstrip("."), rr_str_type, addr[0], "upstream")
            )

            if rr_qtype == qtype_num:
                rdata_cls = rdata_map.get(rr_str_type)
                if rdata_cls:
                    rep.add_answer(RR(str(rr.rname).rstrip("."), rr_qtype, rdata=rdata_cls(val), ttl=ttl))
        conn.commit()
    else:
        rep.header.rcode = RCODE.SERVFAIL

    sock.sendto(rep.pack(), addr)
