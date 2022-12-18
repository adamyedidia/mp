from datetime import timedelta
from typing import Any

from enum import Enum
import pygame


DAGGER_RANGE = 100


class Garb(Enum):
    BOOTS = 'boots'


def garb_to_pygame_image(garb: Garb) -> Any:
    if garb == Garb.BOOTS:
        return pygame.image.load('assets/boots.png')


def garb_max_age(garb: Garb) -> timedelta:
    if garb == Garb.BOOTS:
        return timedelta(seconds=15)
    else:
        raise Exception('Not implemented')