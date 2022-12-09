from typing import Any, Optional

from enum import Enum
from typing import TYPE_CHECKING
import pygame
import json
from redis_utils import rget, rset
from weapon import weapon_to_pygame_image, Weapon
if TYPE_CHECKING:
    from player import Player


class ItemCategory(Enum):
    WEAPON = 'weapon'


class ItemType(Enum):
    BOW = 'bow'
    DAGGER = 'dagger'


class Item:
    def __init__(self, id: int, x: int, y: int, category: ItemCategory, type: ItemType):
        self.id = id
        self.x = x
        self.y = y
        self.category = category
        self.type = type

    def draw(self, canvas: Any) -> None:
        if self.category == ItemCategory.WEAPON:
            image_surface = pygame.transform.scale(weapon_to_pygame_image(Weapon(self.type.value)), (50, 50)).convert_alpha()
            canvas.blit(image_surface, (self.x - 25, self.y - 25))        


NEXT_ITEM_ID_REDIS_KEY = 'next_item_id'


def generate_next_item_id(*, client_id: Optional[int]) -> int:
    next_item_id = int(rget(NEXT_ITEM_ID_REDIS_KEY, client_id=client_id) or '0')
    rset(NEXT_ITEM_ID_REDIS_KEY, next_item_id + 1, client_id=client_id)
    return next_item_id
