from typing import Any

from enum import Enum
import pygame


class Weapon(Enum):
    BOW = 'bow'
    DAGGER = 'dagger'


def weapon_to_pygame_image(weapon: Weapon) -> Any:
    if weapon == Weapon.BOW: 
        return pygame.image.load('assets/bow_and_arrow.png')
    elif weapon == Weapon.DAGGER:
        return pygame.image.load('assets/dagger.png')
