import socket
import requests
from dnslib import DNSRecord, QTYPE

DNS_PORT = 8053
DOH_URL = "https://dns.google/dns-query"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", DNS_PORT))

print(f"DNS Server with DoH running on port {DNS_PORT} ...")

while True:
    data, addr = sock.recvfrom(512)
    try:
        request = DNSRecord.parse(data)
        request.header.rd = 1

        doh_data = request.pack()

        response = requests.post(
            DOH_URL,
            headers={
                "Content-Type": "application/dns-message",
                "Accept": "application/dns-message"
            },
            data=doh_data,
            timeout=5
        )

        if response.status_code == 200:
            sock.sendto(response.content, addr)
        else:
            sock.sendto(request.reply().pack(), addr)

    except Exception as e:
        print("[ERROR]", e)
        sock.sendto(request.reply().pack(), addr)
