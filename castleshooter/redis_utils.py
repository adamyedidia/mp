import redis as r
from typing import Any, Optional

from contextlib import contextmanager
import redis_lock as rl

redis = r.Redis(connection_pool=r.ConnectionPool(host='localhost', port=6379, db=0))

def rset(key: str, value: Any) -> bool:
    return redis.set(key, value)

def rget(key: str) -> Optional[str]:
    return val.decode() if (val := redis.get(key)) is not None else None

@contextmanager
def redis_lock(key: str) -> Any:
    lock = rl.Lock(redis, key)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

