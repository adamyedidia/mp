from datetime import datetime

from command import Command


class Announcement:
    def __init__(self, idempotency_key: str, time: datetime, message: str) -> None:
        self.idempotency_key = idempotency_key
        self.time = time
        self.message = message


def get_announcement_idempotency_key_for_command(command: Command) -> str:
    return f'command:{command.id}'
