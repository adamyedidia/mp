from socket import socket
import pygame
from pygame import Color

from redis_utils import rget

from player import Player
from canvas import Canvas
from client_utils import Client, client

from packet import send_without_retry

class Game:
    def __init__(self, w: int, h: int, client: Client, socket: socket):
        self.width = w
        self.height = h
        self.client = client
        self.s = socket
        self.player_number = self.client.id if self.client.id is not None else -1
        self.players: dict[int, Player] = {}
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
        data = f'player_state_{self.player_number}|{self.player.to_json()};'
        print(data)
        send_without_retry(self.s, data, client_id=client.id)

    def update_from_server(self) -> None:
        active_players = rget('active_players', client_id=client.id)
        if not active_players:
            return
        player_numbers = [int(i) for i in active_players.split(',')]
        for p in player_numbers:
            if p not in self.players and p != self.player_number:
                self.players[p] = Player(50, 50, Color(0, 255, 255))
            player_state = rget(f'player_state_{p}', client_id=client.id)
            if player_state is not None:
                self.players[p].from_json(player_state)
