from pydantic import BaseModel
from typing import Optional

class DNSQuery(BaseModel):
    domain: str
    qtype: str = "A"

class DNSRecordModel(BaseModel):
    domain: str
    qtype: str
    value: str
    ttl: int = 60
    prorarity: Optional[int] = None
