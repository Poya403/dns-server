import socket
import sqlite3
import time
from dnslib import DNSRecord, RR, A, QTYPE, RCODE

DNS_PORT = 53
DB_FILE = "dns.db"
UPSTREAM_DNS = ("8.8.8.8", 53)
CACHE_TTL = 60

cache = {}


conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE,
    ip TEXT
)
""")
conn.commit()


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", DNS_PORT))


def ask_upstream_dns(domain):
    query = DNSRecord.question(domain)
    upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    upstream_sock.settimeout(3)

    try:
        upstream_sock.sendto(query.pack(), UPSTREAM_DNS)
        data, _ = upstream_sock.recvfrom(512)
        response = DNSRecord.parse(data)

        for rr in response.rr:
            if rr.rtype == QTYPE.A:
                return str(rr.rdata)

    except Exception:
        return None

    finally:
        upstream_sock.close()

    return None


def get_from_cache(domain):
    if domain in cache:
        ip, expire_time = cache[domain]
        if time.time() < expire_time:
            return ip
        else:
            del cache[domain]
    return None


def save_to_cache(domain, ip):
    cache[domain] = (ip, time.time() + CACHE_TTL)


def main(data, address):
    request = DNSRecord.parse(data)
    reply = request.reply()

    domain = str(request.q.qname).rstrip(".").lower()
    qtype = QTYPE[request.q.qtype]

    print(f"Query from {address[0]} -> {domain} ({qtype})")

    if qtype != "A":
        reply.header.rcode = RCODE.NOTIMP
        return reply

    # Cache
    ip = get_from_cache(domain)
    if ip:
        reply.add_answer(RR(domain, QTYPE.A, rdata=A(ip)))
        return reply

    # Database
    cursor.execute("SELECT ip FROM records WHERE domain = ?", (domain,))
    row = cursor.fetchone()

    if row:
        ip = row[0]
        reply.add_answer(RR(domain, QTYPE.A, rdata=A(ip)))
        return reply

    # Upstream DNS
    ip = ask_upstream_dns(domain)
    if ip:
        save_to_cache(domain, ip)

        cursor.execute("""
            INSERT INTO records(domain, ip)
            VALUES (?, ?)
            ON CONFLICT(domain) DO UPDATE SET ip = excluded.ip
        """, (domain, ip))
        conn.commit()

        reply.add_answer(RR(domain, QTYPE.A, rdata=A(ip)))
    else:
        reply.header.rcode = RCODE.NXDOMAIN

    return reply


print(f"DNS Server running on port {DNS_PORT} ...")

while True:
    data, address = sock.recvfrom(512)
    response = main(data, address)
    sock.sendto(response.pack(), address)
