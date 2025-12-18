import socket
import sqlite3
import time
from dnslib import DNSRecord, RR, A, QTYPE, RCODE

DNS_PORT = 53
DB_FILE = "dns.db"
UPSTREAM_DNS = ("8.8.8.8", DNS_PORT)
DEFAULT_TTL = 60

cache = {}

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE,
    ip TEXT,
    ttl INTEGER DEFAULT 60
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY,
    domain TEXT,
    user_ip TEXT,
    src TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""CREATE TABLE IF NOT EXISTS blacklist (domain TEXT UNIQUE)""")
conn.commit()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", DNS_PORT))

def ask_upstream_dns(domain):
    query = DNSRecord.question(domain, QTYPE.A)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3)

    try:
        sock.sendto(query.pack() , UPSTREAM_DNS)
        data, _ = sock.recvfrom(512)
        response = DNSRecord.parse(data)

        for rr in response.rr:
            if rr.rtype == QTYPE.A:
                ip = str(rr.rdata)
                ttl = rr.ttl
                return ip, ttl
    except:
        return None, None
    finally:
        sock.close()


def main(data, address):
    request = DNSRecord.parse(data)
    reply = request.reply()
    domain = str(request.q.qname).rstrip(".").lower()
    qtype = QTYPE[request.q.qtype]

    print(f"Query from {address[0]} -> {domain} ({qtype})")

    if qtype != "A":
        reply.header.rcode = RCODE.NOTIMP
        return reply

    cursor.execute("SELECT 1 FROM blacklist WHERE domain = ?", (domain,))
    if cursor.fetchone():
        reply.header.rcode = RCODE.NXDOMAIN
        return reply
    
    if domain in cache:
        ip, expire_time = cache[domain]
        if time.time() < expire_time:
            reply.add_answer(RR(domain, QTYPE.A, rdata=A(ip)))
            cursor.execute(
                "INSERT INTO logs(domain, user_ip, src) VALUES (?, ?, ?)",
                (domain, address[0], "cache")
            )
            conn.commit()
            return reply
        else:
            del cache[domain]

    cursor.execute("SELECT ip FROM records WHERE domain = ?", (domain,))
    row = cursor.fetchone()
    if row:
        ip = row[0]
        cache[domain] = (ip, time.time() + DEFAULT_TTL)
        reply.add_answer(RR(domain, QTYPE.A, rdata=A(ip)))
        cursor.execute(
            "INSERT INTO logs(domain, user_ip, src) VALUES (?, ?, ?)",
            (domain, address[0], "data base")
        )
        conn.commit()
        return reply

    ip, ttl = ask_upstream_dns(domain)
    if ip:
        cache[domain] = (ip, time.time() + ttl if ttl else DEFAULT_TTL) 
        cursor.execute("""
            INSERT INTO records(domain, ip, ttl)
            VALUES (?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET ip = excluded.ip
        """, (domain, ip, ttl))
        conn.commit()
        reply.add_answer(RR(domain, QTYPE.A, rdata=A(ip)))
        cursor.execute(
            "INSERT INTO logs(domain, user_ip, src) VALUES (?, ?, ?)",
            (domain, address[0], "upstream")
        )
        conn.commit()
    else:
        reply.header.rcode = RCODE.NXDOMAIN

    return reply

print(f"DNS Server running on port {DNS_PORT} ...")

while True:
    data, address = sock.recvfrom(512)
    response = main(data, address)
    sock.sendto(response.pack(), address)
