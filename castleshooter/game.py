from socket import socket
import pygame
from pygame import Color
from client import Client
from redis_utils import rget


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


class Player():
    width = height = 50

    def __init__(self, startx: int, starty: int, color: Color=Color(255, 0, 0)):
        self.x = startx
        self.y = starty
        self.velocity: int = 2
        self.color = color

    def draw(self, g: pygame.surface.Surface):
        pygame.draw.rect(g, self.color ,(self.x, self.y, self.width, self.height), 0)

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


class Game:

    def __init__(self, w: int, h: int, client: Client, socket: socket):
        self.width = w
        self.height = h
        self.client = client
        self.s = socket
        self.player_number = self.client.id if self.client.id is not None else -1
        self.players = {}
        self.player = Player(50, 50)
        self.canvas = Canvas(self.width, self.height, "Testing...")

    def run(self):
        clock = pygame.time.Clock()
        run = True
        while run:
            clock.tick(60)

            if self.player_number < 0:
                self.player_number = self.client.id if self.client.id is not None else -1
                self.players[self.player_number] = self.player
                continue

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    run = False

                if event.type == pygame.K_ESCAPE:
                    run = False

            keys = pygame.key.get_pressed()

            for input in [pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN]:
                if keys[input]:
                    self.player.move(input)
                    self.player.make_valid_position(self.width, self.height)
                    self.send_data()

            # Interpret Network Stuff
            self.update_from_server()

            # Update Canvas
            self.canvas.draw_background()
            for player in self.players.values():
                player.draw(self.canvas.get_canvas())
            self.canvas.update()

        pygame.quit()

    def send_data(self) -> None:
        data = f'player_state_{self.player_number}:{self.player.x},{self.player.y}'
        self.s.sendall(bytes(data, 'utf-8'))

    def update_from_server(self) -> None:
        active_players = rget('client_active_players')
        if not active_players:
            return
        player_numbers = [int(i) for i in active_players.split(',')]
        for p in player_numbers:
            if p not in self.players and p != self.player_number:
                self.players[p] = Player(50, 50, Color(0, 255, 255))
            player_state = rget(f'client_player_state_{p}')
            if player_state is not None:
                state = [int(i) for i in player_state.split(',')]
                self.players[p].x, self.players[p].y = state
