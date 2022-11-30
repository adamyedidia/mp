from typing import Optional


class Client:
    def __init__(self) -> None:
        self.id = -1

    def set_id(self, id: int) -> None:
        self.id = id


client = Client()