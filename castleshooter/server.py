from settings import PORT, SERVER
import socket
from typing import Any
from redis_utils import rset, rget, redis_lock, flushall
import gevent
from _thread import start_new_thread

_CLICK_COUNTER_REDIS_KEY = 'click_counter'

class Connection():
    def __init__(self, id: int, conn: Any, addr: tuple[str, int]) -> None:
        self.id = id
        self.conn = conn
        self.addr = addr


    def __repr__(self) -> str:
        return f"<Connection {self.id}: {self.addr}>"


class Game():

    def get_num_clicks(self) -> int:
        return int(rget(_CLICK_COUNTER_REDIS_KEY) or '0')

    def increment_num_clicks(self):
        num_clicks = self.get_num_clicks()
        with redis_lock('click_counter_lock'):
            rset(_CLICK_COUNTER_REDIS_KEY, num_clicks + 1)

    def handle_data_from_client(self, data: str):
        if data == 'click':
            print('incrementing')
            self.increment_num_clicks()
            

def _get_new_connection_id(active_connections_by_id: dict[int, Connection]) -> int:
    if active_connections_by_id:
        return max(active_connections_by_id.keys()) + 1
    return 0


def handle_connection(connection: Connection, game: Game) -> None:
    print('handling connection!')
    connection.conn.send(b'hello!')
    while True:
        data = connection.conn.recv(4096).decode()
        print(data)
        game.handle_data_from_client(data)


def main() -> None:
    flushall()
    active_connections_by_id: dict[int, Connection] = {}

    game = Game()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((SERVER, PORT))
        s.listen()
        print('Starting the server!')
        while True:
            conn, addr = s.accept()
            new_connection_id = _get_new_connection_id(active_connections_by_id)
            connection = Connection(new_connection_id, conn, addr)
            active_connections_by_id[new_connection_id] = connection
            
            start_new_thread(handle_connection, (connection, game))

            print(f'New connection: {connection}')
    except BaseException as e:
        print(f'Error: {e}. Closing the socket')
        s.close()


if __name__ == '__main__':
    main()