from pydantic import BaseModel

class DNSQuery(BaseModel):
    name: str
    type: str

class DNSResponse(BaseModel):
    name: str
    type: str
    value: str
    ttl: int
