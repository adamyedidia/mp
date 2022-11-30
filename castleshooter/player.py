from typing import Optional
import pygame
from pygame import Color
import json
from item import Item, Sword
from json.decoder import JSONDecodeError

from utils import to_optional_int

class Player():
    def __init__(self, client_id: int, startx: int, starty: int, 
                 dest_x: Optional[int] = None, dest_y: Optional[int] = None,
                 color: Color=Color(255, 0, 0), 
                 healthbar: Optional['HealthBar'] = None):
        self.client_id = client_id
        self.x = startx
        self.y = starty
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.width = 50
        self.height = 50

        self.healthbar: HealthBar = healthbar if healthbar is not None else HealthBar()
        self.item: Item = Sword()

        self.speed: int = 2
        self.color = color

    def draw(self, g: pygame.surface.Surface):
        pygame.draw.rect(g, self.color ,(self.x, self.y, self.width, self.height), 0)
        self.healthbar.draw(g, self.x, self.y)
        self.item.draw(g, self.x, self.y)

    def move(self, input: int) -> None:
        if input == pygame.K_RIGHT:
            self.x += self.speed
        elif input == pygame.K_LEFT:
            self.x -= self.speed
        elif input == pygame.K_UP:
            self.y -= self.speed
        elif input == pygame.K_DOWN:
            self.y += self.speed

    def make_valid_position(self, w: int, h: int) -> None:
        self.x = max(0, self.x)
        self.x = min(w-self.width, self.x)
        self.y = max(0, self.y)
        self.y = min(h-self.height, self.y)

    def to_json(self):
        return json.dumps({
            'client_id': self.client_id,
            'x': self.x,
            'y': self.y,
            'dest_x': self.dest_x,
            'dest_y': self.dest_y,
            'healthbar': self.healthbar.to_json(),
            # 'item': self.item.to_json(),
        })

    @classmethod
    def from_json(cls, d: dict) -> 'Player':
        return Player(client_id=d['client_id'], startx=d['x'], starty=d['y'], 
                      dest_x=to_optional_int(d['dest_x']), dest_y=to_optional_int(d['dest_y']),
                      healthbar=HealthBar.from_json(d['healthbar']))


    def update_from_json(self, j: str):
        d: dict = json.loads(j)
        self.x = d['x']
        self.y = d['y']
        self.dest_x = d['dest_x']
        self.dest_y = d['dest_y']
        self.healthbar.update_from_json(d['healthbar'])
        # self.item.from_json(d['item'])  # TODO: fix this


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
        return HealthBar(hp=d['hp'])

    def update_from_json(self, j: str):
        d: dict = json.loads(j)
        self.hp = d['hp']
        self.update_color()
