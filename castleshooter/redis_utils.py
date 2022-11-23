import redis as r
from typing import Any, Callable, Optional

from contextlib import contextmanager
import redis_lock as rl

redis = r.Redis(connection_pool=r.ConnectionPool(host='localhost', port=6379, db=0))

def _get_redis_key(key: str, client_id: Optional[int] = None) -> str:
    prefix = f'client:{client_id}' if client_id else 'server'
    return f'{prefix}:{key}'


def rset(key: str, value: Any, client_id: Optional[int] = None) -> Optional[bool]:
    redis_key = _get_redis_key(key, client_id=client_id)
    redis.publish(redis_key, str(value))
    return redis.set(_get_redis_key(key, client_id=client_id), str(value))


def rget(key: str, client_id: Optional[int] = None) -> Optional[str]:
    return (val.decode() 
            if (val := redis.get(_get_redis_key(key, client_id=client_id))) is not None 
            else None)


def rlisten(key: str, callback: Callable[[Optional[str]], None], 
            client_id: Optional[int] = None) -> None:
    pubsub = redis.pubsub()
    pubsub.subscribe(_get_redis_key(key, client_id=client_id))
    for item in pubsub.listen():
        print(item)
        if item['type'] == 'message':
            data = item['data']
            if isinstance(data, bytes):
                callback(data.decode())
            elif data is None:
                callback(None)
            else:
                callback(str(data))


def flushall() -> None:
    redis.flushall()


@contextmanager
def redis_lock(key: str, client_id: Optional[int] = None) -> Any:
    lock = rl.Lock(redis, _get_redis_key(key, client_id=client_id))
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

