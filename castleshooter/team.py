from typing import Optional, TYPE_CHECKING
import random

from enum import Enum
if TYPE_CHECKING:
    from player import Player

from redis_utils import rget
from client_utils import get_player_number_from_client_id

import json

class Team(Enum):
    RED = 'red'
    BLUE = 'blue'


def team_to_color(team: Optional[Team]) -> tuple[int, int, int]:
    if team == Team.BLUE:
        return (128, 128, 255)
    elif team == Team.RED:
        return (255, 64, 64)
    else:
        return (192, 192, 192)


def get_team_for_client_id(client_id: int) -> Team:
    if random.random() < 0.5:
        return Team.RED
    else:
        return Team.BLUE


def flip_team(team: Team) -> Team:
    if team == Team.RED:
        return Team.BLUE
    else:
        return Team.RED


def rotate_team(current_team: Optional[Team], my_team: Team) -> Optional[Team]:
    if current_team is None:
        return my_team
    elif current_team == my_team:
        return flip_team(current_team)
    else:
        return None


def get_true_teams(client_id: Optional[int], game_name: Optional[str] = None, exclude_my_client_id: Optional[int] = None) -> dict[Team, list[int]]:
    red_team_cid = [cid for cid in json.loads(rget('red_team', client_id=client_id, game_name=game_name) or '[]') if cid != exclude_my_client_id]
    assert red_team_cid
    blue_team_cid = [cid for cid in json.loads(rget('blue_team', client_id=client_id, game_name=game_name) or '[]') if cid != exclude_my_client_id]
    assert blue_team_cid

    return {
        Team.RED: [get_player_number_from_client_id(cid, client_id=client_id, game_name=game_name) for cid in red_team_cid], 
        Team.BLUE: [get_player_number_from_client_id(cid, client_id=client_id, game_name=game_name) for cid in blue_team_cid],
    }
