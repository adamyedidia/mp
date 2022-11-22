from settings import PORT, SERVER
from socket import socket
from typing import Any


class Connection():
    def __init__(self, id: int, conn: Any, addr: tuple[str, int]) -> None:
        self.id = id
        self.conn = conn
        self.addr = addr


    def __repr__(self) -> str:
        return f"<Connection {self.id}: {self.addr}>"



class Game():
    def __init__(self):
        self.num_clicks = 0
    
    def 


def _get_new_connection_id(active_connections_by_id: dict[int, Connection]) -> int:
    if active_connections_by_id:
        return max(active_connections_by_id.keys()) + 1
    return 0


def main() -> None:
    active_connections_by_id: dict[int, Connection] = {}

    game = Game()
    s = socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((SERVER, PORT))
    s.listen()
    while True:
        conn, addr = s.accept()
        new_connection_id = _get_new_connection_id(active_connections_by_id)
        active_connections_by_id[new_connection_id] = Connection(new_connection_id, conn, addr)
        
        print(f'New connection: {connection}')




if __name__ == '__main__':
    main()