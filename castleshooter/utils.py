from typing import Any, Optional


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
