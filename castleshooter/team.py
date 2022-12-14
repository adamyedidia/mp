from typing import Optional
import random

from enum import Enum


class Team(Enum):
    RED = 'red'
    BLUE = 'blue'


def team_to_color(team: Optional[Team]) -> tuple[int, int, int]:
    if team == Team.BLUE:
        return (0, 0, 255)
    elif team == Team.RED:
        return (255, 0, 0)
    else:
        return (128, 128, 128)


def get_team_for_client_id(client_id: int) -> Team:
    if random.random() < 0.5:
        return Team.RED
    else:
        return Team.BLUE
