from settings import PORT, SERVER
from socket import socket
from typing import Any
from redis_utils import rset, rget, redis_lock


class Connection():
    def __init__(self, id: int, conn: Any, addr: tuple[str, int]) -> None:
        self.id = id
        self.conn = conn
        self.addr = addr


    def __repr__(self) -> str:
        return f"<Connection {self.id}: {self.addr}>"


class Game():
    _CLICK_COUNTER_REDIS_KEY = 'click_counter'

    def get_num_clicks(self) -> int:
        return int(rget(_CLICK_COUNTER_REDIS_KEY)) or 0

    def increment_num_clicks(self):
        num_clicks = self.get_num_clicks()
        with redis_lock('click_counter_lock'):
            rset(_CLICK_COUNTER_REDIS_KEY, num_clicks + 1)

    def handle_data_from_client(self, data: str):
        if data == 'click':
            self.increment_num_clicks()
            

def _get_new_connection_id(active_connections_by_id: dict[int, Connection]) -> int:
    if active_connections_by_id:
        return max(active_connections_by_id.keys()) + 1
    return 0


def handle_connection(connection: Connection, game: Game) -> None:
    while True:
        data = conn.recv(4096).decode()
        game.handle_data_from_client(data)


def main() -> None:
    active_connections_by_id: dict[int, Connection] = {}

    game = Game()
    s = socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((SERVER, PORT))
    s.listen()
    while True:
        conn, addr = s.accept()
        new_connection_id = _get_new_connection_id(active_connections_by_id)
        connection = Connection(new_connection_id, conn, addr)
        active_connections_by_id[new_connection_id] = connection
        
        gevent.spawn(handle_connection, connection, game)

        print(f'New connection: {connection}')




if __name__ == '__main__':
    main()