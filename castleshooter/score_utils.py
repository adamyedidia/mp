import pygame
from team import Team, team_to_color
from utils import draw_3_texts_centered_on_rectangle_inner


def draw_score_centered_on_rectangle(g: pygame.surface.Surface, red_points: int, blue_points: int, x: int, y: int, width: int, height: int, font_size: int) -> None:
    font = pygame.font.SysFont('comicsans', font_size)

    red_score_text = font.render(str(red_points), True, team_to_color(Team.RED))
    dash_text = font.render('  -  ', True, (0,0,0))
    blue_score_text = font.render(str(blue_points), True, team_to_color(Team.BLUE))

    draw_3_texts_centered_on_rectangle_inner(g, red_score_text, dash_text, blue_score_text, x, y, width, height)