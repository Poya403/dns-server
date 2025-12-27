import socket
import sqlite3
import time
import os
from threading import Thread
from dnslib import DNSRecord, RR, QTYPE, RCODE, A, NS, MX, CNAME
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

def query_dns(domain: str, qtype: str = "A"):
    qtype = qtype.upper()
    qtype_num = QTYPE[qtype]
    key = (domain, qtype_num)
    valid_rrs = []
    cached_list = cache.get(key, [])
    for val, expire in cached_list:
        if time.time() < expire:
            valid_rrs.append((val, expire))
    if valid_rrs:
        return [{"domain": domain, "qtype": qtype, "value": val, "ttl": DEFAULT_TTL} for val, _ in valid_rrs]
    conn, cursor = get_connection()
    cursor.execute("SELECT value, ttl FROM records WHERE domain=? AND qtype=?", (domain, qtype))
    rows = cursor.fetchall()
    if rows:
        result = []
        for value, ttl in rows:
            ttl = ttl or DEFAULT_TTL
            valid_rrs.append((value, time.time() + ttl))
            result.append({"domain": domain, "qtype": qtype, "value": value, "ttl": ttl})
        cache[key] = valid_rrs
        return result
    response = ask_upstream(domain, qtype)
    if response:
        result = []
        for rr in response.rr:
            rr_qtype = rr.rtype
            rr_str_type = QTYPE[rr_qtype]
            val = str(rr.rdata)
            ttl = rr.ttl or DEFAULT_TTL
            k = (str(rr.rname).rstrip("."), rr_qtype)
            cache.setdefault(k, []).append((val, time.time() + ttl))
            conn, cursor = get_connection()
            cursor.execute("""
                INSERT INTO records(domain, qtype, value, ttl)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(domain, qtype, value) DO UPDATE SET ttl = excluded.ttl
            """, (str(rr.rname).rstrip("."), rr_str_type, val, ttl))
            conn.commit()
            if rr_str_type == qtype:
                result.append({"domain": str(rr.rname).rstrip("."), "qtype": rr_str_type, "value": val, "ttl": ttl})
        return result
    return []

def handle_request(data, addr):
    req = DNSRecord.parse(data)
    rep = req.reply()

    domain = str(req.q.qname).rstrip(".").lower()
    qtype_str = QTYPE[req.q.qtype]

    key = (domain, qtype_str)

    # -------- 1. CACHE --------
    cached = cache.get(key, [])
    valid = [(v, e) for v, e in cached if time.time() < e]

    if valid:
        for value, _ in valid:
            if qtype_str == "MX":
                pref, exch = value.split()
                rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(int(pref), exch), ttl=DEFAULT_TTL))
            else:
                rep.add_answer(RR(domain, req.q.qtype, rdata=rdata_map[qtype_str](value), ttl=DEFAULT_TTL))

        cache[key] = valid
        conn, cur = get_connection()
        cur.execute(
            "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
            (domain, qtype_str, addr[0], "cache")
        )
        conn.commit()
        sock.sendto(rep.pack(), addr)
        return

    cache.pop(key, None)

    # -------- 2. DATABASE --------
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
                rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(int(pref), exch), ttl=ttl))
            else:
                rep.add_answer(RR(domain, req.q.qtype, rdata=rdata_map[qtype_str](value), ttl=ttl))

        cache[key] = new_cache
        cur.execute(
            "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
            (domain, qtype_str, addr[0], "database")
        )
        conn.commit()
        sock.sendto(rep.pack(), addr)
        return

    # -------- 3. UPSTREAM --------
    response = ask_upstream(domain, qtype_str)
    if not response:
        rep.header.rcode = RCODE.SERVFAIL
        sock.sendto(rep.pack(), addr)
        return

    all_rrs = response.rr + response.auth + response.ar

    for rr in all_rrs:
        rr_domain = str(rr.rname).rstrip(".").lower()
        rr_type = QTYPE[rr.rtype]
        ttl = rr.ttl or DEFAULT_TTL

        if rr_type == "MX":
            value = f"{rr.rdata.preference} {rr.rdata.exchange}"
        else:
            value = str(rr.rdata)

        expire = time.time() + ttl
        cache.setdefault((rr_domain, rr_type), []).append((value, expire))

        conn, cur = get_connection()
        cur.execute("""
            INSERT INTO records(domain, qtype, value, ttl)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(domain, qtype, value)
            DO UPDATE SET ttl=excluded.ttl
        """, (rr_domain, rr_type, value, ttl))

        cur.execute(
            "INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)",
            (rr_domain, rr_type, addr[0], "upstream")
        )
        conn.commit()

        if rr_domain == domain and rr_type == qtype_str:
            if rr_type == "MX":
                pref, exch = value.split()
                rep.add_answer(RR(domain, QTYPE.MX, rdata=MX(int(pref), exch), ttl=ttl))
            else:
                rep.add_answer(RR(domain, rr.rtype, rdata=rdata_map[rr_type](value), ttl=ttl))

    sock.sendto(rep.pack(), addr)

def start_udp_server():
    while True:
        try:
            data, addr = sock.recvfrom(512)
            Thread(target=handle_request, args=(data, addr)).start()
        except ConnectionResetError:
            continue