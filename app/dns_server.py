import socket
import sqlite3
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

rdata_map = {"A": A, "NS": NS, "MX": MX, "CNAME": CNAME}

def ask_upstream(domain, qtype="A"):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    try:
        q = DNSRecord.question(domain, qtype)
        s.sendto(q.pack(), UPSTREAM_DNS)
        r = DNSRecord.parse(s.recvfrom(512)[0])
        return r
    except:
        return None
    finally:
        s.close()


def store_record(domain: str, qtype: str, value: str, ttl: int):
    """ذخیره رکورد در دیتابیس به صورت رشته‌ای"""
    conn, cur = get_connection()
    cur.execute("""
        INSERT INTO records(domain, qtype, value, ttl)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(domain, qtype, value) DO UPDATE SET ttl=excluded.ttl
    """, (domain, qtype, value, ttl))
    conn.commit()
    conn.close()


def query_dns(domain: str, qtype: str = "A"):

    qtype = qtype.upper()
    key = (domain, qtype)

    valid_rrs = [(v, e) for v, e in cache.get(key, []) if time.time() < e]
    if valid_rrs:
        return [{"domain": domain, "qtype": qtype, "value": val, "ttl": DEFAULT_TTL} for val, _ in valid_rrs]

    conn, cursor = get_connection()
    cursor.execute("SELECT value, ttl FROM records WHERE domain=? AND qtype=?", (domain, qtype))
    rows = cursor.fetchall()
    if rows:
        result = []
        new_cache = []
        for value, ttl in rows:
            ttl = ttl or DEFAULT_TTL
            expire = time.time() + ttl
            new_cache.append((value, expire))
            result.append({"domain": domain, "qtype": qtype, "value": value, "ttl": ttl})
        cache[key] = new_cache
        conn.close()
        return result

    response = ask_upstream(domain, qtype)
    if not response:
        return []

    result = []
    all_rrs = response.rr + response.auth + response.ar
    for rr in all_rrs:
        rr_domain = str(rr.rname).rstrip(".").lower()
        rr_type = QTYPE[rr.rtype]
        ttl = rr.ttl or DEFAULT_TTL

        if rr_type == "MX":
            value = f"{rr.rdata.preference} {str(rr.rdata.exchange)}"
        else:
            value = str(rr.rdata)

        expire = time.time() + ttl
        cache.setdefault((rr_domain, rr_type), []).append((value, expire))

        store_record(rr_domain, rr_type, value, ttl)

        if rr_domain == domain and rr_type == qtype:
            result.append({"domain": domain, "qtype": qtype, "value": value, "ttl": ttl})

    return result


def handle_request(data, addr):
    try:
        req = DNSRecord.parse(data)
        rep = req.reply()
        domain = str(req.q.qname).rstrip(".").lower()
        qtype_str = QTYPE[req.q.qtype]

        valid = [(v, e) for v, e in cache.get((domain, qtype_str), []) if time.time() < e]
        if valid:
            for value, _ in valid:
                if qtype_str == "MX":
                    pref, exch = value.split()
                    if not exch.endswith("."):
                        exch += "."
                    rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(int(pref), DNSLabel(exch)), ttl=DEFAULT_TTL))
                else:
                    rep.add_answer(RR(domain, req.q.qtype, rdata=rdata_map[qtype_str](value), ttl=DEFAULT_TTL))
            cache[(domain, qtype_str)] = valid
            conn, cur = get_connection()
            cur.execute(
                "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
                (domain, qtype_str, addr[0], "cache")
            )
            conn.commit()
            conn.close()
            sock.sendto(rep.pack(), addr)
            return

        cache.pop((domain, qtype_str), None)

        conn, cur = get_connection()
        cur.execute(
            "SELECT value, ttl FROM records WHERE domain=? AND qtype=?",
            (domain, qtype_str)
        )
        rows = cur.fetchall()
        if rows:
            new_cache = []
            for value, ttl in rows:
                ttl = ttl or DEFAULT_TTL
                expire = time.time() + ttl
                new_cache.append((value, expire))
                if qtype_str == "MX":
                    pref, exch = value.split()
                    if not exch.endswith("."):
                        exch += "."
                    rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(int(pref), DNSLabel(exch)), ttl=ttl))
                else:
                    rep.add_answer(RR(domain, req.q.qtype, rdata=rdata_map[qtype_str](value), ttl=ttl))
            cache[(domain, qtype_str)] = new_cache
            cur.execute(
                "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
                (domain, qtype_str, addr[0], "database")
            )
            conn.commit()
            conn.close()
            sock.sendto(rep.pack(), addr)
            return

        upstream_records = query_dns(domain, qtype_str)
        if not upstream_records:
            rep.header.rcode = RCODE.SERVFAIL
            sock.sendto(rep.pack(), addr)
            return

        for r in upstream_records:
            if r["qtype"] == "MX":
                pref, exch = r["value"].split()
                if not exch.endswith("."):
                    exch += "."
                rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(int(pref), DNSLabel(exch)), ttl=r["ttl"]))
            else:
                rep.add_answer(RR(domain, req.q.qtype, rdata=rdata_map[r["qtype"]](r["value"]), ttl=r["ttl"]))

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
            data, addr = sock.recvfrom(512)
            Thread(target=handle_request, args=(data, addr), daemon=True).start()
        except ConnectionResetError:
            continue

