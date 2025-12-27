import time
from typing import List, Tuple

# key = (domain, qtype) -> list of (value, expire_time)
cache = {}

def get_from_cache(domain: str, qtype: str) -> List[str]:
    key = (domain.lower(), qtype.upper())
    results = []
    valid = []
    for val, expire in cache.get(key, []):
        if time.time() < expire:
            results.append(val)
            valid.append((val, expire))
    if valid:
        cache[key] = valid
    else:
        cache.pop(key, None)
    return results

def add_to_cache(domain: str, qtype: str, value: str, ttl: int):
    key = (domain.lower(), qtype.upper())
    expire_time = time.time() + ttl
    cache.setdefault(key, []).append((value, expire_time))
