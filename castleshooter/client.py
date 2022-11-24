import game
from settings import PORT, SERVER
import socket
from typing import Any
from redis_utils import rset, rget, redis_lock    
from _thread import start_new_thread

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
        if data.startswith('active_players:'):
            key, data = data.split(':')
            rset(f'client_{key}', data)
        if data.startswith('player_state_'):
            key, data = data.split(':')
            rset(f'client_{key}', data)


def client_main() -> None:

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER, PORT))

    g = game.Game(500,500, client, s)
    start_new_thread(listen_for_server_updates, (s,))
    g.run()


if __name__ == '__main__':
    client_main()