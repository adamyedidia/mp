import pygame

class Item():
    def __init__(self, range: int):
        self.range = range

    def draw(self, x, y):
        pass


class Sword(Item):
    def __init__(self):
        Item(50)

    def draw(self, g: pygame.surface.Surface, x: int, y: int):
        pygame.draw.rect(g, (0,0,0), (x+30, y+30, 15, 5))
        pygame.draw.rect(g, (0,0,0), (x+35, y+15, 5, 27))
