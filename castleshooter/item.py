from typing import Any, Optional

from enum import Enum
from typing import TYPE_CHECKING
import pygame
import json
from redis_utils import rget, rset
from weapon import weapon_to_pygame_image, Weapon
from garb import garb_to_pygame_image, Garb
if TYPE_CHECKING:
    from player import Player


class ItemCategory(Enum):
    WEAPON = 'weapon'
    GARB = 'garb'


class ItemType(Enum):
    # Weapons
    BOW = 'bow'
    DAGGER = 'dagger'
    FLASHLIGHT = 'flashlight'

    # Garb
    BOOTS = 'boots'
    ARMOR = 'armor'


class Item:
    def __init__(self, id: int, x: int, y: int, category: ItemCategory, type: ItemType):
        self.id = id
        self.x = x
        self.y = y
        self.category = category
        self.type = type

    def draw(self, canvas: Any, x_offset: int, y_offset: int) -> None:
        if self.category == ItemCategory.WEAPON:
            image_surface = pygame.transform.scale(weapon_to_pygame_image(Weapon(self.type.value)), (50, 50)).convert_alpha()
        elif self.category == ItemCategory.GARB:
            image_surface = pygame.transform.scale(garb_to_pygame_image(Garb(self.type.value)), (50, 50)).convert_alpha()
        else:
            raise Exception('Not implemented')
        canvas.blit(image_surface, (self.x - x_offset - 25, self.y - y_offset - 25))        


NEXT_ITEM_ID_REDIS_KEY = 'next_item_id'


def generate_next_item_id(*, client_id: Optional[int]) -> int:
    next_item_id = int(rget(NEXT_ITEM_ID_REDIS_KEY, client_id=client_id) or '0')
    rset(NEXT_ITEM_ID_REDIS_KEY, next_item_id + 1, client_id=client_id)
    return next_item_id
