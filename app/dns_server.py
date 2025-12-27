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
    qtype_num = req.q.qtype
    qtype_str = QTYPE[qtype_num]
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
        conn, cursor = get_connection()
        cursor.execute("INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)", (domain, qtype_str, addr[0], "cache"))
        conn.commit()
        sock.sendto(rep.pack(), addr)
        return
    else:
        cache.pop(key, None)

    conn, cursor = get_connection()
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
        conn, cursor = get_connection()
        cursor.execute("INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)", (domain, qtype_str, addr[0], "database"))
        conn.commit()
        sock.sendto(rep.pack(), addr)
        return
    response = ask_upstream(domain, qtype_str)
    if response:
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
            
            conn, cursor = get_connection()
            cursor.execute("INSERT INTO logs(domain, qtype, user_ip, src) VALUES (?, ?, ?, ?)", (str(rr.rname).rstrip("."), rr_str_type, addr[0], "upstream"))
            if rr_qtype == qtype_num:
                rdata_cls = rdata_map.get(rr_str_type)
                if rdata_cls:
                    rep.add_answer(RR(str(rr.rname).rstrip("."), rr_qtype, rdata=rdata_cls(val), ttl=ttl))
        conn.commit()
    else:
        rep.header.rcode = RCODE.SERVFAIL
    sock.sendto(rep.pack(), addr)

def start_udp_server():
    while True:
        data, addr = sock.recvfrom(512)
        Thread(target=handle_request, args=(data, addr)).start()