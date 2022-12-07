from typing import Any, Optional

import pygame

MAX_GAME_STATE_SNAPSHOTS = 5
SNAPSHOTS_CREATED_EVERY = 1
LOG_CUTOFF = 1000


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


def draw_text_centered_on_rectangle(g: pygame.surface.Surface, message: str, x: int, y: int, width: int, height: int, font_size: int) -> None:
    font = pygame.font.SysFont('comicsans', font_size)
    text = font.render(message, True, (0,0,0))
    text_rect = text.get_rect()
    rectangle_center = (x + width/2, y + height/2)
    g.blit(text, (int(rectangle_center[0] - text_rect.width/2), int(rectangle_center[1] - text_rect.height/2)))
    # pygame.draw.rect(g, self.color, (int(math.ceil(self.x - self.width / 2)), int(math.ceil(self.y - self.height / 2)), self.width, self.height), 0)
