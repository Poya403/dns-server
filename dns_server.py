import socket
from dnslib import DNSRecord, RR, A, QTYPE, RCODE
import sqlite3
port = 53
db_file = "dns.db"

createTableSql = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE,
    ip TEXT
)
"""
selectDataSql = """
SELECT ip FROM records WHERE domain = ?
"""

conn = sqlite3.connect(db_file)
cursor = conn.cursor()
cursor.execute(createTableSql)
conn.commit()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", port))

print(f"DNS Server running on port {port} ...")

while True:
    data , address = sock.recvfrom(512)

    request = DNSRecord.parse(data)
    reply = request.reply()

    domain = str(request.q.qname).rstrip(".").lower()
    qtype = QTYPE[request.q.qtype]

    print(f"Query from {address[0]} -> {domain} ({qtype})")

    if qtype == "A": 
        cursor.execute(selectDataSql,(domain,))
        result = cursor.fetchone()

        if result is not None:
            ip = result[0]
            reply.add_answer(
                RR(domain, QTYPE.A, rdata=A(ip))
            )
        else: reply.header.rcode =  RCODE.NXDOMAIN
    else:
        reply.header.rcode = RCODE.NOTIMP

    sock.sendto(reply.pack(), address)
