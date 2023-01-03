from typing import Any, Optional

import pygame

MAX_GAME_STATE_SNAPSHOTS = 5
SNAPSHOTS_CREATED_EVERY = 1
LOG_CUTOFF = 1000
SPECIAL_LOBBY_MANAGER_GAME_NAME = 'lobby_manager'


def to_optional_str(val: Any) -> Optional[str]:
    if isinstance(val, bytes):
        return val.decode()
    elif val is None:
        return None
    else:
        return str(val)


def to_optional_int(val: Any) -> Optional[int]:
    if val is None or val == 'None':
        return None
    else:
        return int(val)


def remove_nones(d: dict) -> dict:
    return {key: value for key, value in d.items() if value is not None}


def draw_3_texts_centered_on_rectangle_inner(g: pygame.surface.Surface, text1: Any, text2: Any, text3: Any, x: int, y: int, width: int, height: int) -> None:
    text1_rect = text1.get_rect()
    text2_rect = text2.get_rect()
    text3_rect = text3.get_rect()
    rectangle_center = (x + width/2, y + height/2)
    combined_width = text1_rect.width + text2_rect.width + text3_rect.width
    g.blit(text1, (int(rectangle_center[0] - combined_width/2), int(rectangle_center[1] - text1_rect.height/2)))
    g.blit(text2, (int(rectangle_center[0] - combined_width/2 + text1_rect.width), int(rectangle_center[1] - text1_rect.height/2)))
    g.blit(text3, (int(rectangle_center[0] - combined_width/2 + text1_rect.width + text2_rect.width), int(rectangle_center[1] - text1_rect.height/2)))


def draw_text_centered_on_rectangle_inner(g: pygame.surface.Surface, text: Any, x: int, y: int, width: int, height: int) -> None:
    text_rect = text.get_rect()
    rectangle_center = (x + width/2, y + height/2)
    g.blit(text, (int(rectangle_center[0] - text_rect.width/2), int(rectangle_center[1] - text_rect.height/2)))


def draw_text_centered_on_rectangle(g: pygame.surface.Surface, message: str, x: int, y: int, width: int, height: int, font_size: int) -> None:
    font = pygame.font.SysFont('comicsans', font_size)
    text = font.render(message, True, (0,0,0))
    draw_text_centered_on_rectangle_inner(g, text, x, y, width, height)


def draw_text_list(g: pygame.surface.Surface, messages: list[str], x: int, y: int, box_width: int, box_height: int, font_size: int) -> None:
    current_y = y
    for message in messages:
        draw_text_centered_on_rectangle(g, message, x, current_y, box_width, box_height, font_size)
        current_y += box_height


def clamp(lower, x, upper):
    return min(max(lower, x), upper)


GAME_WIDTH = 3000
GAME_HEIGHT = 3000
MAX_SCORE = 20


def clamp_to_game_x(x: int) -> int:
    return clamp(0, x, GAME_WIDTH)
def clamp_to_game_y(y: int) -> int:
    return clamp(0, y, GAME_HEIGHT)


logs = []
