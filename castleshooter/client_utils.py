from typing import Optional
from team import Team

from redis_utils import rget


class Client:
    def __init__(self) -> None:
        self.id = -1
        self.team: Optional[Team] = None
        self.player_number: Optional[int] = None

    def set_id(self, id: int) -> None:
        self.id = id

    def set_team(self, team: Team) -> None:
        self.team = team

    def set_player_number(self, player_number: int) -> None:
        self.player_number = player_number


client = Client()


def get_player_number_from_client_id(from_client_id: int, *, client_id: Optional[int]) -> int:
    print(f'player_number:{from_client_id}')
    raw_player_number = rget(f'player_number:{from_client_id}', client_id=client_id)
    assert raw_player_number is not None
    return int(raw_player_number)


def get_client_id_from_player_number(player_number: int, *, client_id: int) -> int:
    assert client_id is not None
    raw_client_id = rget(f'client_id:{player_number}', client_id=client_id)
    assert raw_client_id is not None
    return int(raw_client_id)

