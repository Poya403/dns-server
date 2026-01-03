import socket
import time
import os
from threading import Thread
from dnslib import DNSRecord, RR, QTYPE, RCODE, A, NS, MX, CNAME, DNSLabel
from app.data_base import get_connection

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "db", "records.db")
DNS_PORT = 53
UPSTREAM_DNS = ("8.8.8.8", 53)
DEFAULT_TTL = 60

cache = {}
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", DNS_PORT))

rdata_map = {"A": A, "NS": NS, "CNAME": CNAME}


def ask_upstream(domain, qtype="A"):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
    try:
        q = DNSRecord.question(domain, qtype)
        s.sendto(q.pack(), UPSTREAM_DNS)
        data, _ = s.recvfrom(2048)
        return DNSRecord.parse(data)
    except Exception as e:
        print(f"Upstream request failed: {e}")
        return None
    finally:
        s.close()


def store_record(domain: str, qtype: str, value: str, ttl: int, prorarity: int = None):
    if value is None:
        value = ""
    value = str(value).strip()
    conn, cur = get_connection()
    cur.execute("""
        INSERT INTO records(domain, qtype, value, ttl, prorarity)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(domain, qtype, value) DO UPDATE 
            SET ttl=excluded.ttl, prorarity=excluded.prorarity
    """, (domain, qtype, value, ttl, prorarity))
    conn.commit()
    conn.close()


def query_dns(domain: str, qtype: str = "A"):
    qtype = qtype.upper()
    key = (domain, qtype)

    # cache
    valid_rrs = [(v, e) for v, e in cache.get(key, []) if time.time() < e]
    if valid_rrs:
        return [{"domain": domain, "qtype": qtype, "value": val, "ttl": DEFAULT_TTL, "prorarity": None} 
                for val, _ in valid_rrs]

    # data base
    conn, cursor = get_connection()
    if qtype == "MX":
        cursor.execute("SELECT value, ttl, prorarity FROM records WHERE domain=? AND qtype=?", (domain, qtype))
    else:
        cursor.execute("SELECT value, ttl FROM records WHERE domain=? AND qtype=?", (domain, qtype))
    rows = cursor.fetchall()
    result = []
    new_cache = []
    for row in rows:
        if qtype == "MX":
            value, ttl, prorarity = row
        else:
            value, ttl = row
            prorarity = None

        # cleanup value
        if value is None or not str(value).strip():
            if qtype == "MX":
                value = "mail." + domain
            else:
                value = ""
        value = str(value).strip()
        ttl = ttl or DEFAULT_TTL
        expire = time.time() + ttl
        new_cache.append((value, expire))
        result.append({"domain": domain, "qtype": qtype, "value": value, "ttl": ttl, "prorarity": prorarity})

    cache[key] = new_cache
    conn.close()

    if result:
        return result

    # upstream
    response = ask_upstream(domain, qtype)
    if not response:
        return []

    for rr in response.rr + response.auth + response.ar:
        rr_domain = str(rr.rname).rstrip(".").lower()
        rr_type = QTYPE[rr.rtype]
        ttl = rr.ttl or DEFAULT_TTL

        if rr_type == "MX":
            try:
                mx_str = str(rr.rdata).strip()
                parts = mx_str.split(None, 1)
                if len(parts) == 2:
                    prorarity = int(parts[0])
                    if prorarity < 0:
                        prorarity = 0
                    elif prorarity > 65535:
                        prorarity = 10
                    value = parts[1].rstrip(".")
                else:
                    prorarity = 10
                    value = mx_str
            except:
                prorarity = 10
                value = str(rr.rdata).rstrip(".")

            if not value.strip():
                value = "mail." + rr_domain
        else:
            value = str(rr.rdata)
            prorarity = None

        value = str(value).strip()
        expire = time.time() + ttl
        cache.setdefault((rr_domain, rr_type), []).append((value, expire))
        store_record(rr_domain, rr_type, value, ttl, prorarity)

        if rr_domain == domain and rr_type == qtype:
            result.append({"domain": domain, "qtype": qtype, "value": value, "ttl": ttl, "prorarity": prorarity})

    return result


def handle_request(data, addr):
    try:
        req = DNSRecord.parse(data)
        rep = req.reply()
        domain = str(req.q.qname).rstrip(".").lower()
        qtype_str = QTYPE[req.q.qtype]

        records = query_dns(domain, qtype_str)

        if not records:
            rep.header.rcode = RCODE.SERVFAIL
            sock.sendto(rep.pack(), addr)
            return

        for r in records:
            if r["qtype"] == "MX":
                priority = r["prorarity"]
                if priority is None or priority < 0 or priority > 65535:
                    priority = 10
                host = str(r["value"] or "").strip()
                if not host:
                    host = "mail." + domain
                host = host.rstrip(".") + "."
                rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(priority, DNSLabel(host)), ttl=r["ttl"]))
            else:
                rep.add_answer(RR(domain, req.q.qtype, rdata=rdata_map[r["qtype"]](r["value"]), ttl=r["ttl"]))

        # log
        conn, cur = get_connection()
        cur.execute(
            "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
            (domain, qtype_str, addr[0], "upstream")
        )
        conn.commit()
        conn.close()

        sock.sendto(rep.pack(), addr)

    except Exception as e:
        print(f"Warning in handle_request: {e}")


def start_udp_server():
    while True:
        try:
            data, addr = sock.recvfrom(2048)
            Thread(target=handle_request, args=(data, addr), daemon=True).start()
        except ConnectionResetError:
            continue


if __name__ == "__main__":
    print(f"Starting DNS server on UDP port {DNS_PORT}...")
    start_udp_server()
