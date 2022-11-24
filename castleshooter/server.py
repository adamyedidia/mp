from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock, flushall, rlisten
import gevent
from _thread import start_new_thread
from time import sleep

_CLICK_COUNTER_REDIS_KEY = 'click_counter'

def _send(conn: Any, message: str) -> None:
    conn.sendall(bytes(message, 'utf-8'))


class Connection:
    def __init__(self, id: int, conn: Any, addr: tuple[str, int]) -> None:
        self.id = id
        self.conn = conn
        self.addr = addr

    def __repr__(self) -> str:
        return f"<Connection {self.id}: {self.addr}>"


class Game:
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


def _handle_incoming_connection(connection: Connection, game: Game) -> None:
    print('handling incoming connection!')
    while True:
        data = connection.conn.recv(4096).decode()
        print(data)
        game.handle_data_from_client(data)


def _handle_outgoing_connection(connection: Connection, game: Game) -> None:
    def _handle_click_counter_change(value: Optional[str]) -> None:
        _send(connection.conn, f'num_clicks:{value or 0}')

    rlisten(_CLICK_COUNTER_REDIS_KEY, _handle_click_counter_change)


def main() -> None:
    flushall()
    active_connections_by_id: dict[int, Connection] = {}

    game = Game()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((socket.gethostbyname(socket.gethostname()), PORT))
        s.listen()
        print('Starting the server!')
        while True:
            conn, addr = s.accept()
            new_connection_id = _get_new_connection_id(active_connections_by_id)
            connection = Connection(new_connection_id, conn, addr)
            active_connections_by_id[new_connection_id] = connection
            
            sleep(0.01)
            _send(conn, f'client_id:{new_connection_id}')
            sleep(0.001)
            print(f'Startup value: {rget(_CLICK_COUNTER_REDIS_KEY) or 0}')
            _send(conn, f'num_clicks:{rget(_CLICK_COUNTER_REDIS_KEY) or 0}')

            start_new_thread(_handle_incoming_connection, (connection, game))
            start_new_thread(_handle_outgoing_connection, (connection, game))

            print(f'New connection: {connection}')
    except BaseException as e:
        print(f'Error: {e}. Closing the socket')
        s.close()


if __name__ == '__main__':
    main()