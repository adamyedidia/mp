from typing import Optional
from team import Team


class Client:
    def __init__(self) -> None:
        self.id = -1
        self.team: Optional[Team] = None

    def set_id(self, id: int) -> None:
        self.id = id

    def set_team(self, team: Team) -> None:
        self.team = team


client = Client()