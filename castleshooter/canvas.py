import pygame

class Canvas:

    def __init__(self, w: int, h: int, name: str="None"):
        self.width = w
        self.height = h
        self.screen: pygame.surface.Surface = pygame.display.set_mode((w,h))
        pygame.display.set_caption(name)

    @staticmethod
    def update():
        pygame.display.update()

    def get_canvas(self):
        return self.screen

    def draw_background(self):
        self.screen.fill((255,255,255))