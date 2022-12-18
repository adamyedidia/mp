from datetime import timedelta
from typing import Any

from enum import Enum
import pygame


DAGGER_RANGE = 100


class Garb(Enum):
    BOOTS = 'boots'
    ARMOR = 'armor'


def garb_to_pygame_image(garb: Garb) -> Any:
    if garb == Garb.BOOTS:
        return pygame.image.load('assets/boots.png')
    elif garb == Garb.ARMOR:
        return pygame.image.load('assets/armor.png')
    else:
        raise Exception('Not implemented')


def garb_max_age(garb: Garb) -> timedelta:
    return timedelta(seconds=15)