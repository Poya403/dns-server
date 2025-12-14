import socket
from dnslib import DNSRecord, RR, A, QTYPE

port = 53
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("127.0.0.1",port))
print(f"DNS Server running on port {port} ...")

while True:
    data, addr = sock.recvfrom(512)

    request = DNSRecord.parse(data)
    reply = request.reply()

    qname = request.q.qname
    qtype = QTYPE[request.q.qtype]

    print(f"Query received: {qname} ({qtype})")

    reply.add_answer(
        RR(
            rname=qname,
            rtype=QTYPE.A,
            rclass=1,
            ttl=60,
            rdata=A("127.0.0.1")
        )
    )

    sock.sendto(reply.pack(), addr)
