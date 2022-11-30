from typing import Any, Optional


MAX_GAME_STATE_SNAPSHOTS = 5
SNAPSHOTS_CREATED_EVERY = 1


def to_optional_str(val: Any) -> Optional[str]:
    if isinstance(val, bytes):
        return val.decode()
    elif val is None:
        return None
    else:
        return str(val)


def to_optional_int(val: Any) -> Optional[int]:
    if val is None or val == 'None':
        return None
    else:
        return int(val)


def remove_nones(d: dict) -> dict:
    return {key: value for key, value in d.items() if value is not None}
