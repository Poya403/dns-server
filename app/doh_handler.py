from fastapi import HTTPException, APIRouter
from app.models import DNSQuery, DNSRecordModel
from app.data_base import add_record, delete_record, get_records
from app.cache import get_cached, set_cache
from app.dns_server import query_dns

router = APIRouter()

@router.get("/query-dns")
def doh_get(domain: str, qtype: str = "A"):
    cached = get_cached(domain, qtype)
    if cached:
        return [{"domain": domain, "qtype": qtype, "value": val, "ttl": 60} for val in cached]

    records = query_dns(domain, qtype)
    if not records:
        raise HTTPException(status_code=404, detail="Record not found")

    set_cache(domain, qtype, [r["value"] for r in records], ttl=records[0]["ttl"])
    return records

@router.post("/query-dns")
def doh_post(query: DNSQuery):
    return doh_get(query.domain, query.qtype)

@router.post("/admin/record")
def add_dns_record(record: DNSRecordModel):
    add_record(record)
    return {"status": "success", "record": record}

@router.delete("/admin/record/{domain}")
def delete_dns_record(domain: str, qtype: str = None):
    delete_record(domain, qtype)
    return {"status": "success", "domain": domain, "qtype": qtype}

@router.get("/admin/records")
async def list_records(domain: str = None, qtype: str = None):
    return get_records(domain, qtype)

# @router.get("/admin/logs")
# def list_logs():
#     conn, cursor = get_connection()
#     cursor.execute("SELECT domain, qtype, user_ip FROM logs ORDER BY id DESC LIMIT 100")
#     rows = cursor.fetchall()
#     conn.close()
#     return [{"domain": r[0], "qtype": r[1], "client_ip": r[2]} for r in rows]