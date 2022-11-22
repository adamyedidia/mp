import redis as r
from typing import Any, Optional

from contextlib import contextmanager
import redis_lock as rl

redis = r.Redis(connection_pool=r.ConnectionPool(host='localhost', port=6379, db=0))

def _get_redis_key(key: str, client: bool = False) -> str:
    prefix = 'client' if client else 'server'
    return f'{client}:{key}'

def rset(key: str, value: Any, client: bool = False) -> bool:
    return redis.set(_get_redis_key(key, client=client), value)

def rget(key: str, client: bool = False) -> Optional[str]:
    return val.decode() if (val := redis.get(_get_redis_key(key, client=client))) is not None else None

def flushall() -> None:
    redis.flushall()

@contextmanager
def redis_lock(key: str, client: bool = False) -> Any:
    lock = rl.Lock(redis, _get_redis_key(key, client=client))
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

