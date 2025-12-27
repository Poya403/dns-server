import time

cache = {}  # key = (domain, qtype) -> list of (value, expire_time)

def get_cached(domain: str, qtype: str):
    key = (domain.lower(), qtype.upper())
    valid = []
    for val, expire in cache.get(key, []):
        if time.time() < expire:
            valid.append((val, expire))
    if valid:
        cache[key] = valid
        return [v for v, e in valid]
    return None

def set_cache(domain: str, qtype: str, values: list, ttl: int):
    key = (domain.lower(), qtype.upper())
    expire_time = time.time() + ttl
    cache[key] = [(v, expire_time) for v in values]
