from typing import Optional
from team import Team

from redis_utils import rget


class Client:
    def __init__(self) -> None:
        self.id = -1
        self.team: Optional[Team] = None
        self.player_number: Optional[int] = None
        self.game_started: bool = False
        self.game_name: Optional[str] = None
        self.ai: bool = False

    def set_id(self, id: int) -> None:
        self.id = id

    def set_team(self, team: Team) -> None:
        self.team = team

    def set_player_number(self, player_number: int) -> None:
        self.player_number = player_number

    def set_game_started(self, game_started: bool) -> None:
        self.game_started = game_started

    def set_game_name(self, game_name: str) -> None:
        self.game_name = game_name


_client = Client()


def get_client(ai_client_id: Optional[int] = None, ai_team: Optional[Team] = None, game_name: Optional[str] = None) -> Client:
    if ai_client_id is None:
        return _client
    assert ai_team
    assert game_name
    client = Client()
    client.id = ai_client_id
    client.team = ai_team
    client.game_name = game_name
    client.game_started = True
    client.ai = True
    return client


def get_player_number_from_client_id(from_client_id: int, *, client_id: Optional[int], game_name: Optional[str] = None) -> int:
    raw_player_number = rget(f'player_number:{from_client_id}', client_id=client_id, game_name=game_name)
    assert raw_player_number is not None
    return int(raw_player_number)


def get_client_id_from_player_number(player_number: int, *, client_id: int, game_name: Optional[str] = None) -> int:
    assert client_id is not None
    raw_client_id = rget(f'client_id:{player_number}', client_id=client_id, game_name=game_name)
    assert raw_client_id is not None
    return int(raw_client_id)

