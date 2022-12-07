from typing import Any, Callable, Optional

from contextlib import contextmanager
from utils import to_optional_str


pretend_redis_dict: dict[str, Optional[str]] = {}

def get_redis() -> Any:
    import redis as r
    return r.Redis(connection_pool=r.ConnectionPool(host='localhost', port=6379, db=0))


def _get_redis_key_prefix(*, client_id: Optional[int]) -> str:
    return f'client:{client_id}' if client_id is not None else 'server'


def _get_redis_key(key: str, *, client_id: Optional[int]) -> str:
    prefix = _get_redis_key_prefix(client_id=client_id)
    return f'{prefix}:{key}'


def _get_redis_key_inverse(redis_key: str, *, client_id: Optional[int]) -> str:
    prefix = _get_redis_key_prefix(client_id=client_id)
    assert redis_key.startswith(prefix)
    return redis_key[len(prefix) + 1:]


def rset(key: str, value: Any, *, client_id: Optional[int]) -> Optional[bool]:
    if client_id is not None:
        old_value = pretend_redis_dict.get(key)
        new_value = to_optional_str(value)
        pretend_redis_dict[key] = to_optional_str(value)
        return old_value != new_value

    redis = get_redis()
    redis_key = _get_redis_key(key, client_id=client_id)
    redis.publish(redis_key, str(value))
    return redis.set(_get_redis_key(key, client_id=client_id), str(value))


def rget(key: str, *, client_id: Optional[int]) -> Optional[str]:
    if client_id is not None:
        return pretend_redis_dict.get(key)

    redis = get_redis()
    return (val.decode() 
            if (val := redis.get(_get_redis_key(key, client_id=client_id))) is not None 
            else None)


# Can only be called from the server
def rlisten(keys: list[str], callback: Callable[[str, Optional[str]], None]) -> None:
    redis = get_redis()
    pubsub = redis.pubsub()
    for key in keys:
        pubsub.subscribe(_get_redis_key(key, client_id=None))
    for item in pubsub.listen():
        if item['type'] == 'message':
            raw_channel = to_optional_str(item['channel'])
            assert raw_channel is not None
            channel = _get_redis_key_inverse(raw_channel, client_id=None)
            data = to_optional_str(item['data'])
            callback(channel, data)


def flushall() -> None:
    redis = get_redis()
    redis.flushall()


# Can only be called from the server; if called with a non-null client_id, just does nothing
@contextmanager
def redis_lock(key: str, *, client_id: Optional[int]) -> Any:
    if client_id is not None:
        yield
    redis = get_redis()        
    import redis_lock as rl
    lock = rl.Lock(redis, _get_redis_key(key, client_id=None))
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

