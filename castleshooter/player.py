import pygame
from pygame import Color
from item import *

class Player():
    def __init__(self, startx: int, starty: int, color: Color=Color(255, 0, 0)):
        self.x = startx
        self.y = starty
        self.width = 50
        self.height = 50

        self.healthbar = HealthBar()
        self.item = Sword()
        
        self.velocity: int = 2
        self.color = color

    def draw(self, g: pygame.surface.Surface):
        pygame.draw.rect(g, self.color ,(self.x, self.y, self.width, self.height), 0)
        self.healthbar.draw(g, self.x, self.y)
        self.item.draw(g, self.x, self.y)

    def move(self, input: int) -> None:
        if input == pygame.K_RIGHT:
            self.x += self.velocity
        elif input == pygame.K_LEFT:
            self.x -= self.velocity
        elif input == pygame.K_UP:
            self.y -= self.velocity
        elif input == pygame.K_DOWN:
            self.y += self.velocity

    def make_valid_position(self, w: int, h: int) -> None:
        self.x = max(0, self.x)
        self.x = min(w-self.width, self.x)
        self.y = max(0, self.y)
        self.y = min(h-self.height, self.y)


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
