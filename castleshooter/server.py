from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock, flushall, rlisten
import gevent
from _thread import start_new_thread
from time import sleep


def _send(conn: Any, message: str) -> None:
    conn.sendall(bytes(message, 'utf-8'))


class Connection:
    def __init__(self, id: int, conn: Any, addr: tuple[str, int]) -> None:
        self.id = id
        self.conn = conn
        self.addr = addr

    def __repr__(self) -> str:
        return f"<Connection {self.id}: {self.addr}>"


class GameState:
    def set_active_players(self, active_connections_by_id: dict):
        client_ids = active_connections_by_id.keys()
        print(f'client_ids: {client_ids}')
        rset('active_players', ','.join(str(i) for i in client_ids))

    def get_active_players(self) -> list[int]:
        active_players = rget('active_players') or ''
        return [int(i) for i in active_players.split(',')]

    def get_player_state(self, player_number: int) -> Optional[str]:
        return rget(f'player_state_{player_number}')

    def handle_data_from_client(self, data: str):
        if data.startswith('player_state'):
            print(f'recieved: {data}')
            key, data = data.split(':')
            rset(key, data)
            

def _get_new_connection_id(active_connections_by_id: dict[int, Connection]) -> int:
    if active_connections_by_id:
        return max(active_connections_by_id.keys()) + 1
    return 0


def _handle_incoming_connection(connection: Connection, game_state: GameState) -> None:
    print('handling incoming connection!')
    while True:
        data = connection.conn.recv(4096).decode()
        print(data)
        game_state.handle_data_from_client(data)


def _handle_outgoing_active_players_connection(connection: Connection) -> None:
    def _handle_active_players_change(value: Optional[str]) -> None:
        _send(connection.conn, f'active_players:{value}')

    rlisten('active_players', _handle_active_players_change)


def _handle_outgoing_player_state_connection(connection: Connection, game_state: GameState) -> None:
    while True:
        active_players = game_state.get_active_players()
        for p in active_players:
            player_state = game_state.get_player_state(p)
            if player_state is not None:
                _send(connection.conn, f'player_state_{p}:{player_state}')
            sleep(.01)
        sleep(.01)


def main() -> None:
    flushall()
    active_connections_by_id: dict[int, Connection] = {}

    game_state = GameState()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(socket.gethostname())
    try:
        s.bind((socket.gethostname(), PORT))
        s.listen()
        print('Starting the server!')
        while True:
            conn, addr = s.accept()
            new_connection_id = _get_new_connection_id(active_connections_by_id)
            connection = Connection(new_connection_id, conn, addr)
            active_connections_by_id[new_connection_id] = connection
            game_state.set_active_players(active_connections_by_id)
            
            sleep(0.01)
            _send(conn, f'client_id:{new_connection_id}')
            sleep(0.001)

            start_new_thread(_handle_incoming_connection, (connection, game_state))
            start_new_thread(_handle_outgoing_active_players_connection, (connection,))
            start_new_thread(_handle_outgoing_player_state_connection, (connection, game_state))

            print(f'New connection: {connection}')
    except BaseException as e:
        print(f'Error: {e}. Closing the socket')
        s.close()


if __name__ == '__main__':
    main()