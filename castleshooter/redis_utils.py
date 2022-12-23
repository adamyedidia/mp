import redis as r
from typing import Any, Callable, Optional

from contextlib import contextmanager
import redis_lock as rl
from utils import to_optional_str

redis = r.Redis(connection_pool=r.ConnectionPool(host='localhost', port=6379, db=0))
pretend_redis_dict: dict[str, Optional[str]] = {}

def _get_redis_key_prefix(*, client_id: Optional[int], game_name: Optional[str]) -> str:
    return f'client:{client_id}' if client_id is not None else f'server:{game_name}'


def _get_redis_key(key: str, *, client_id: Optional[int], game_name: Optional[str]) -> str:
    prefix = _get_redis_key_prefix(client_id=client_id, game_name=game_name)
    return f'{prefix}:{key}'


def _get_redis_key_inverse(redis_key: str, *, client_id: Optional[int], game_name: Optional[str]) -> str:
    prefix = _get_redis_key_prefix(client_id=client_id, game_name=game_name)
    assert redis_key.startswith(prefix)
    return redis_key[len(prefix) + 1:]


def rset(key: str, value: Any, *, client_id: Optional[int], game_name: Optional[str] = None) -> Optional[bool]:
    if client_id is not None:
        old_value = pretend_redis_dict.get(key)
        new_value = to_optional_str(value)
        pretend_redis_dict[key] = to_optional_str(value)
        return old_value != new_value

    assert game_name is not None
    redis_key = _get_redis_key(key, client_id=client_id, game_name=game_name)
    redis.publish(redis_key, str(value))
    return redis.set(_get_redis_key(key, client_id=client_id, game_name=game_name), str(value))


def rget(key: str, *, client_id: Optional[int], game_name: Optional[str] = None) -> Optional[str]:
    if client_id is not None:
        return pretend_redis_dict.get(key)

    assert game_name is not None
    return (val.decode() 
            if (val := redis.get(_get_redis_key(key, client_id=client_id, game_name=game_name))) is not None 
            else None)


# Can only be called from the server
def rlisten(keys: list[str], callback: Callable[[str, Optional[str]], None], game_name: str, break_when: Optional[Callable[[], bool]] = None) -> None:
    pubsub = redis.pubsub()
    for key in keys:
        pubsub.subscribe(_get_redis_key(key, client_id=None, game_name=game_name))
    for item in pubsub.listen():
        if item['type'] == 'message':
            raw_channel = to_optional_str(item['channel'])
            assert raw_channel is not None
            channel = _get_redis_key_inverse(raw_channel, client_id=None, game_name=game_name)
            data = to_optional_str(item['data'])
            callback(channel, data)
        if break_when is not None and break_when():
            break


def flushall() -> None:
    redis.flushall()


# Can only be called from the server; if called with a non-null client_id, just does nothing
@contextmanager
def redis_lock(key: str, *, client_id: Optional[int], game_name: Optional[str] = None) -> Any:
    if client_id is not None:
        yield
    assert game_name is not None
    lock = rl.Lock(redis, _get_redis_key(key, client_id=None, game_name=game_name))
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
