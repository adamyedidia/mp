from enum import Enum
import json
import math
import random
from typing import Optional
import pygame
from direction import to_optional_direction
from utils import to_optional_int

from direction import Direction

def draw_arrow(screen, colour, start, end):
    # https://stackoverflow.com/questions/43527894/drawing-arrowheads-which-follow-the-direction-of-the-line-in-pygame
    pygame.draw.line(screen,colour,start,end,2)
    rotation = math.degrees(math.atan2(start[1]-end[1], end[0]-start[0]))+90
    pygame.draw.polygon(screen, (255, 0, 0), ((end[0]+20*math.sin(math.radians(rotation)), end[1]+20*math.cos(math.radians(rotation))), (end[0]+20*math.sin(math.radians(rotation-120)), end[1]+20*math.cos(math.radians(rotation-120))), (end[0]+20*math.sin(math.radians(rotation+120)), end[1]+20*math.cos(math.radians(rotation+120)))))


class ProjectileType(Enum):
    ARROW = 'arrow'


class Projectile:
    def __init__(self, id: int, startx: int, starty: int, type: ProjectileType,
                 player_id: int,
                 dest_x: Optional[int] = None, dest_y: Optional[int] = None, 
                 source_x: Optional[int] = None, source_y: Optional[int] = None):
        self.id = id
        self.player_id = player_id
        self.x = startx
        self.y = starty
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.source_x = source_x
        self.source_y = source_y

        self.speed: int = 800
        self.type: ProjectileType = type


    def draw(self, g: pygame.surface.Surface):
        if self.type == ProjectileType.ARROW:
            color = (0,0,0)
            arrow_length = 30
            end = (self.x, self.y)
            vector_from_source_to_dest = (self.dest_x - self.source_x, self.dest_y - self.source_y)
            vector_from_source_to_dest_mag = math.sqrt(vector_from_source_to_dest[0] ** 2 + vector_from_source_to_dest[1] ** 2)
            unit_vector_from_source_to_dest = (vector_from_source_to_dest_mag[0] / vector_from_source_to_dest_mag,
                                               vector_from_source_to_dest_mag[1] / vector_from_source_to_dest_mag)
            start = (end[0] - unit_vector_from_source_to_dest[0] * arrow_length, 
                     end[1] - unit_vector_from_source_to_dest[1] * arrow_length)
            draw_arrow(g, color, start, end)

    def to_json(self):
        return json.dumps({
            'id': self.client_id,
            'x': self.x,
            'y': self.y,
            'player_id': self.player_id,
            'dest_x': self.dest_x,
            'dest_y': self.dest_y,
            'source_x': self.source_x,
            'source_y': self.source_y,
            'type': self.type.value,
            # 'item': self.item.to_json(),
        })

    @classmethod
    def from_json(cls, d: dict) -> 'Projectile':
        if isinstance(d, str):
            d = json.loads(d)
        return Projectile(id=d['id'], startx=d['x'], starty=d['y'], type=ProjectileType(d['type']),
                          player_id=d['player_id'],
                          dest_x=to_optional_int(d['dest_x']), dest_y=to_optional_int(d['dest_y']),
                          source_x = to_optional_int(d['source_x']), source_y=to_optional_int(d['source_y']),
                          direction=to_optional_direction(d['direction']))

    def copy(self) -> 'Projectile':
        return Projectile.from_json(self.to_json())            


def generate_projectile_id():
    return random.randint(0, 10_000_000)