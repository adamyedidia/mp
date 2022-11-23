from settings import PORT, SERVER
import socket
from typing import Any
from redis_utils import rset, rget, redis_lock    
import gevent
import pygame
from _thread import start_new_thread
from time import sleep

_NUM_CLICKS_REDIS_KEY = 'num_clicks'

class Client:
    def __init__(self) -> None:
        self.id = None

    def set_id(self, id: int) -> None:
        self.id = id


client = Client()


def listen_for_server_updates(socket: Any) -> None:
    while True:
        data = socket.recv(1024).decode()
        print(f'Received message: {data}')
        if data.startswith('client_id:') and client.id is None:
            _, raw_client_id = data.split(':')
            client.set_id(int(raw_client_id))
        if data.startswith('num_clicks:'):
            if client.id is None:
                print(f'Discarding {data} because client_id is None')
                continue
            _, raw_num_clicks = data.split(':')
            num_clicks = int(raw_num_clicks)
            rset(_NUM_CLICKS_REDIS_KEY, num_clicks, client_id=client.id)


def client_main() -> None:

    width = 700
    height = 700
    win = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Client")
    pygame.font.init()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER, PORT))

    start_new_thread(listen_for_server_updates, (s,))
    while True:
        if client.id is None:
            num_clicks = 0
        else:
            num_clicks = rget(_NUM_CLICKS_REDIS_KEY, client_id=client.id) or 0

        font = pygame.font.SysFont("comicsans", 30)
        win.fill((255, 255, 255))
        text = font.render("Click this window!", True, (255,0,0))
        win.blit(text, (100,200))
        num_clicks_text = font.render(f"Number of clicks so far: {num_clicks}", True, (255,0,0))
        win.blit(num_clicks_text, (100, 300))
        pygame.display.update()
        for event in pygame.event.get():
            if event.type == pygame.MOUSEBUTTONDOWN:
                print('Click detected!')
                s.sendall(b"click")
        sleep(0.001)


if __name__ == '__main__':
    client_main()