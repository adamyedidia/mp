from enum import Enum
from math import sqrt
from typing import Optional
import pygame


class Direction(Enum):
    NORTH = 'north'
    NORTHEAST = 'northeast'
    EAST = 'east'
    SOUTHEAST = 'southeast'
    SOUTH = 'south'
    SOUTHWEST = 'southwest'
    WEST = 'west'
    NORTHWEST = 'northwest'


def direction_to_unit_vector(direction: Direction) -> tuple[float, float]:
    if direction == Direction.NORTH:
        return 0.0, -1.0
    elif direction == Direction.NORTHEAST:
        return sqrt(2)/2, -sqrt(2)/2
    elif direction == Direction.EAST:
        return 1.0, 0.0
    elif direction == Direction.SOUTHEAST:
        return sqrt(2)/2, sqrt(2)/2
    elif direction == Direction.SOUTH:
        return 0.0, 1.0
    elif direction == Direction.SOUTHWEST:
        return -sqrt(2)/2, sqrt(2)/2
    elif direction == Direction.WEST:
        return -1.0, 0.0
    elif direction == Direction.NORTHWEST:
        return -sqrt(2)/2, -sqrt(2)/2
    raise Exception(f'Unrecognized direction {direction}')


def determine_direction_from_keyboard() -> Optional[Direction]:
    pressed = pygame.key.get_pressed()
    north = pressed[pygame.K_w] or pressed[pygame.K_UP]
    east = pressed[pygame.K_d] or pressed[pygame.K_RIGHT]
    south = pressed[pygame.K_s] or pressed[pygame.K_DOWN]
    west = pressed[pygame.K_a] or pressed[pygame.K_LEFT]

    if (north and south) or (east and west):
        return None
    if north:
        if east:
            return Direction.NORTHEAST
        elif west:
            return Direction.NORTHWEST
        else:
            return Direction.NORTH
    elif south:
        if east:
            return Direction.SOUTHEAST
        elif west:
            return Direction.SOUTHWEST
        else:
            return Direction.SOUTH
    elif east:
        return Direction.EAST
    elif west:
        return Direction.WEST
    else:
        return None


def to_optional_direction(raw_direction: Optional[str]) -> Optional[Direction]:
    if raw_direction is None:
        return None
    return Direction(raw_direction)
