from datetime import datetime
import math
from typing import Optional, Union
import pygame
from pygame import Color
import json
from team import team_to_color
from projectile import draw_arrow
from projectile import ARROW_COLOR
from direction import Direction, to_optional_direction
from json.decoder import JSONDecodeError
from weapon import Weapon
from team import Team
from garb import Garb

from utils import to_optional_int, draw_text_centered_on_rectangle

BASE_MAX_HP = 4

class Player():
    def __init__(self, client_id: int, startx: int, starty: int, team: Team, player_number: int, 
    direction: Optional[Direction] = None,
                 dest_x: Optional[int] = None, dest_y: Optional[int] = None,
                 healthbar: Optional['HealthBar'] = None,
                 hp: int = BASE_MAX_HP,
                 arrows_puncturing: Optional[list[list[list[int]]]] = None,
                 speed: int = 200):
        self.client_id = client_id
        self.player_number = player_number
        self.x = startx
        self.y = starty
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.direction = direction
        self.width = 50
        self.height = 50
        self.team = team

        self.healthbar: HealthBar = healthbar if healthbar is not None else HealthBar()
        self.hp = hp
        self.ammo = 0
        self.weapon: Optional[Weapon] = Weapon.DAGGER
        self.garb: Optional[Garb] = None
        self.garb_picked_up_at: Optional[datetime] = None

        self.speed = speed
        self.arrows_puncturing = arrows_puncturing if arrows_puncturing is not None else []

    def draw(self, g: pygame.surface.Surface, x_offset: int, y_offset: int, team: Optional[Team] = None):
        x = int(math.ceil(self.x - x_offset - self.width / 2))
        y = int(math.ceil(self.y - y_offset - self.height / 2))
        pygame.draw.rect(g, team_to_color(team), (x, y, self.width, self.height), 0)
        pygame.draw.rect(g, (0,0,0), (x, y, self.width, self.height), width=2)
        for arrow in self.arrows_puncturing:
            draw_arrow(g, ARROW_COLOR, (arrow[0][0] + self.x - x_offset, arrow[0][1] + self.y - y_offset), (arrow[1][0] + self.x - x_offset, arrow[1][1] + self.y - y_offset))
        draw_text_centered_on_rectangle(g, str(self.player_number), x, y, self.width, self.height, 35)

    def make_valid_position(self, w: int, h: int) -> None:
        self.x = max(0, self.x)
        self.x = min(w-self.width, self.x)
        self.y = max(0, self.y)
        self.y = min(h-self.height, self.y)

    def to_json(self) -> str:
        return json.dumps({
            'client_id': self.client_id,
            'player_number': self.player_number,
            'x': self.x,
            'y': self.y,
            'dest_x': self.dest_x,
            'dest_y': self.dest_y,
            'healthbar': self.healthbar.to_json(),
            'direction': self.direction.value if self.direction is not None else None,
            'arrows_puncturing': self.arrows_puncturing,
            'team': self.team.value,
            'speed': self.speed,
        })

    @classmethod
    def from_json(cls, d: Union[dict, str]) -> 'Player':
        if isinstance(d, str):
            d = json.loads(d)
        assert isinstance(d, dict)
        return Player(client_id=d['client_id'], startx=d['x'], starty=d['y'], 
                      dest_x=to_optional_int(d['dest_x']), dest_y=to_optional_int(d['dest_y']),
                      healthbar=HealthBar.from_json(d['healthbar']), 
                      player_number=d['player_number'],
                      direction=to_optional_direction(d['direction']),
                      arrows_puncturing=d['arrows_puncturing'],
                      team=Team(d['team']),
                      speed=d['speed'])

    def copy(self) -> 'Player':
        return Player.from_json(self.to_json())

    def update_from_json(self, j: str) -> None:
        d: dict = json.loads(j)
        self.x = d['x']
        self.y = d['y']
        self.dest_x = d['dest_x']
        self.dest_y = d['dest_y']
        self.direction = to_optional_direction(d['direction'])
        self.healthbar.update_from_json(d['healthbar'])

    def update_info_from_inferred_game_state(self, player: 'Player') -> None:
        self.x = player.x
        self.y = player.y
        self.dest_x = player.dest_x
        self.dest_y = player.dest_y
        self.direction = player.direction
        self.speed = player.speed


class HealthBar():
    def __init__(self, hp: int = 2):
        self.hp = hp
        self.color = Color(0, 255, 0)  # green

    def draw(self, g: pygame.surface.Surface, x: int, y: int):
        pygame.draw.rect(g, (0,0,0), (x, y, 50, 10))
        pygame.draw.rect(g, self.color, (x+2, y+2, 23*self.hp, 6))

    def update_color(self):
        if self.hp == 2:
            self.color = Color(0, 255, 0)  # green
        elif self.hp == 1:
            self.color = Color(255, 255, 0)  # yellow
        elif self.hp == 0:
            self.color = Color(255, 0, 0)  # red

    def damage(self):
        self.hp = max(0, self.hp - 1)
        self.update_color()

    def heal(self):
        self.hp = min(2, self.hp + 1)
        self.update_color()

    def to_json(self):
        return json.dumps({
            'hp': self.hp,
        })
    
    @classmethod
    def from_json(cls, d: dict) -> 'HealthBar':
        if isinstance(d, str):
            d = json.loads(d)
        return HealthBar(hp=d['hp'])

    def update_from_json(self, j: str):
        d: dict = json.loads(j)
        self.hp = d['hp']
        self.update_color()
