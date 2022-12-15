from typing import Optional
import random

from enum import Enum


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
