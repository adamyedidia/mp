from typing import TYPE_CHECKING
import pygame
if TYPE_CHECKING:
    from player import Player


class Item():
    def __init__(self, range: int = 0):
        self.range = range

    def draw(self, g: pygame.surface.Surface, x, y):
        pass

    def use(self, using_player: 'Player', affected_players: list['Player']):
        pass

    def hit_box(self):
        # TODO: this function will return a function that decides
        #  whether another player's coordinates x, y are within a hitbox
        #  or something like that
        pass


class Sword(Item):
    def __init__(self):
        Item(50)

    def draw(self, g: pygame.surface.Surface, x: int, y: int):
        pygame.draw.rect(g, (0,0,0), (x+30, y+30, 15, 5))
        pygame.draw.rect(g, (0,0,0), (x+35, y+15, 5, 27))

    def use(self, using_player: 'Player', affected_players: list['Player']):
        using_player.item = Item()
        for damaged_player in affected_players:
            damaged_player.healthbar.damage()
