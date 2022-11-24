import redis as r
from typing import Any, Callable, Optional

from contextlib import contextmanager
import redis_lock as rl

redis = r.Redis(connection_pool=r.ConnectionPool(host='localhost', port=6379, db=0))

def _get_redis_key_prefix(client_id: Optional[int] = None) -> str:
    return f'client:{client_id}' if client_id is not None else 'server'


def _get_redis_key(key: str, client_id: Optional[int] = None) -> str:
    prefix = _get_redis_key_prefix(client_id=client_id)
    return f'{prefix}:{key}'


def _get_redis_key_inverse(redis_key: str, client_id: Optional[int] = None) -> str:
    prefix = _get_redis_key_prefix(client_id=client_id)
    assert redis_key.startswith(prefix)
    return redis_key[len(prefix) + 1:]


def _to_optional_str(val: Any) -> Optional[str]:
    if isinstance(val, bytes):
        return val.decode()
    elif val is None:
        return None
    else:
        return str(val)


def rset(key: str, value: Any, client_id: Optional[int] = None) -> Optional[bool]:
    redis_key = _get_redis_key(key, client_id=client_id)
    redis.publish(redis_key, str(value))
    return redis.set(_get_redis_key(key, client_id=client_id), str(value))


def rget(key: str, client_id: Optional[int] = None) -> Optional[str]:
    return (val.decode() 
            if (val := redis.get(_get_redis_key(key, client_id=client_id))) is not None 
            else None)


def rlisten(keys: list[str], callback: Callable[[str, Optional[str]], None], 
            client_id: Optional[int] = None) -> None:
    pubsub = redis.pubsub()
    for key in keys:
        pubsub.subscribe(_get_redis_key(key, client_id=client_id))
    for item in pubsub.listen():
        print(item)
        if item['type'] == 'message':
            raw_channel = _to_optional_str(item['channel'])
            assert raw_channel is not None
            channel = _get_redis_key_inverse(raw_channel, client_id=client_id)
            data = _to_optional_str(item['data'])
            callback(channel, data)


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

