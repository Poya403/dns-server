from fastapi import APIRouter, Request, HTTPException
from typing import List
from app.data_base import Database
from app.cache import get_from_cache, add_to_cache
from app.models import DNSQuery, DNSResponse

router = APIRouter()
db = Database()

DEFAULT_TTL = 60

@router.get("/query-dns", response_model=List[DNSResponse])
async def query_dns_get(name: str, type: str):
    return await resolve_dns(name, type)

@router.post("/query-dns", response_model=List[DNSResponse])
async def query_dns_post(query: DNSQuery):
    return await resolve_dns(query.name, query.type)

async def resolve_dns(domain: str, qtype: str) -> List[DNSResponse]:
    cached = get_from_cache(domain, qtype)
    if cached:
        return [DNSResponse(name=domain, type=qtype.upper(), value=v, ttl=DEFAULT_TTL) for v in cached]
    
    records = db.get_records(domain, qtype)
    if records:
        responses = []
        for val, ttl in records:
            add_to_cache(domain, qtype, val, ttl)
            responses.append(DNSResponse(name=domain, type=qtype.upper(), value=val, ttl=ttl))
        return responses

    raise HTTPException(status_code=404, detail="DNS record not found")
