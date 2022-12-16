from enum import Enum
import json
import math
import random
from typing import TYPE_CHECKING, Optional, Union
import pygame
from direction import to_optional_direction
from utils import to_optional_int

from direction import Direction
if TYPE_CHECKING:
    from player import Player


def draw_arrow(screen, colour, start, end):
    # https://stackoverflow.com/questions/43527894/drawing-arrowheads-which-follow-the-direction-of-the-line-in-pygame
    pygame.draw.line(screen,colour,start,end,2)
    rotation = math.degrees(math.atan2(start[1]-end[1], end[0]-start[0]))+90
    pygame.draw.polygon(screen, (0, 100, 0), ((end[0]+20*math.sin(math.radians(rotation)), end[1]+20*math.cos(math.radians(rotation))), (end[0]+20*math.sin(math.radians(rotation-120)), end[1]+20*math.cos(math.radians(rotation-120))), (end[0]+20*math.sin(math.radians(rotation+120)), end[1]+20*math.cos(math.radians(rotation+120)))))


class ProjectileType(Enum):
    ARROW = 'arrow'


ARROW_LENGTH = 30
ARROW_COLOR = (0,0,0)


class Projectile:
    def __init__(self, id: int, startx: int, starty: int, type: ProjectileType,
                 player_id: int, dest_x: int, dest_y: int, source_x: int, source_y: int,
                 friends: Optional[list[int]] = None):
        self.id = id
        self.player_id = player_id
        self.x = startx
        self.y = starty
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.source_x = source_x
        self.source_y = source_y

        self.speed: int = 300
        self.type: ProjectileType = type

        # client_ids of friendly players
        self.friends = friends if friends is not None else []

    def draw(self, g: pygame.surface.Surface, x_offset: int, y_offset: int):
        if self.type == ProjectileType.ARROW:
            color = ARROW_COLOR
            arrow_length = ARROW_LENGTH
            end = (self.x - x_offset, self.y - y_offset)
            vector_from_source_to_dest = (self.dest_x - self.source_x, self.dest_y - self.source_y)
            vector_from_source_to_dest_mag = math.sqrt(vector_from_source_to_dest[0] ** 2 + vector_from_source_to_dest[1] ** 2)
            unit_vector_from_source_to_dest = (vector_from_source_to_dest[0] / vector_from_source_to_dest_mag,
                                               vector_from_source_to_dest[1] / vector_from_source_to_dest_mag)
            start = (end[0] - unit_vector_from_source_to_dest[0] * arrow_length, 
                     end[1] - unit_vector_from_source_to_dest[1] * arrow_length)
            draw_arrow(g, color, start, end)

    def get_start_of_arrow(self) -> list[int]:
        end = (self.x, self.y)
        arrow_length = ARROW_LENGTH
        vector_from_source_to_dest = (self.dest_x - self.source_x, self.dest_y - self.source_y)
        vector_from_source_to_dest_mag = math.sqrt(vector_from_source_to_dest[0] ** 2 + vector_from_source_to_dest[1] ** 2)
        unit_vector_from_source_to_dest = (vector_from_source_to_dest[0] / vector_from_source_to_dest_mag,
                                            vector_from_source_to_dest[1] / vector_from_source_to_dest_mag)
        return [int(end[0] - unit_vector_from_source_to_dest[0] * arrow_length), 
                int(end[1] - unit_vector_from_source_to_dest[1] * arrow_length)]

    def to_json(self) -> str:
        return json.dumps({
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'player_id': self.player_id,
            'dest_x': self.dest_x,
            'dest_y': self.dest_y,
            'source_x': self.source_x,
            'source_y': self.source_y,
            'type': self.type.value,
            'friends': self.friends,
            # 'item': self.item.to_json(),
        })

    @classmethod
    def from_json(cls, d: Union[dict, str]) -> 'Projectile':
        if isinstance(d, str):
            d = json.loads(d)
        assert isinstance(d, dict)    
        return Projectile(id=d['id'], startx=d['source_x'], starty=d['source_y'], type=ProjectileType(d['type']),
                          player_id=d['player_id'],
                          dest_x=int(d['dest_x']), dest_y=int(d['dest_y']),
                          source_x = int(d['source_x']), source_y=int(d['source_y']),
                          friends=d['friends'])

    def copy(self) -> 'Projectile':
        return Projectile.from_json(self.to_json())            


def generate_projectile_id():
    return random.randint(0, 10_000_000)


def projectile_intersects_player(projectile: Projectile, player: 'Player') -> bool:
    if (projectile.x > player.x - player.width/2 + 1
            and projectile.x < player.x + player.width/2 - 1
            and projectile.y > player.y - player.height/2 + 1
            and projectile.y < player.y + player.height/2 - 1):
        return True
    return False