import json
from utils import SNAPSHOTS_CREATED_EVERY, LOG_CUTOFF
from command import Command, store_command
from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock, flushall, rlisten
import gevent
from _thread import start_new_thread
from time import sleep
from packet import (
    Packet, send_with_retry, send_without_retry, send_ack, packet_ack_redis_key, 
    packet_handled_redis_key
)
import game


_SUBSCRIPTION_KEYS = ['active_players', 
                      'most_recent_game_state_snapshot',
                      'commands_by_player',
                      'commands_by_projectile']


class Connection:
    def __init__(self, id: int, conn: Any, addr: tuple[str, int]) -> None:
        self.id = id
        self.conn = conn
        self.addr = addr

    def __repr__(self) -> str:
        return f"<Connection {self.id}: {self.addr}>"


stored_data: list[str] = []


def _clear_stored_data(stored_data: list[str]) -> None:
    while stored_data:
        del stored_data[0]


class GameState:
    def set_active_players(self, active_connections_by_id: dict):
        client_ids = active_connections_by_id.keys()
        rset('active_players', ','.join(str(i) for i in client_ids), client_id=None)

    def get_active_players(self) -> list[int]:
        active_players = rget('active_players', client_id=None) or ''
        return [int(i) for i in active_players.split(',')]

    def handle_payload_from_client(self, payload: str, packet: Packet):
        if payload.startswith('command'):
            _, data = payload.split('|')
            assert packet.client_id is not None
            store_command(Command.from_json(json.loads(data)), client_id=None, for_client=packet.client_id)
            

    def _handle_datum(self, conn: Any, datum: str) -> None:
        print(f'received: {datum[:LOG_CUTOFF]}\n')
        packet = Packet.from_str(datum)
        packet_id = packet.id
        payload = packet.payload
        if packet.is_ack:
            assert packet_id is not None
            # Record in redis that the message has been acked
            print(f'Received ack for {packet}')
            rset(packet_ack_redis_key(packet_id), '1', client_id=None)
        elif packet_id is None:
            assert payload is not None
            self.handle_payload_from_client(payload, packet)
        else:
            assert payload is not None
            with redis_lock(f'handle_payload_from_client|{packet.client_id}|{packet.id}', 
                            client_id=None):
                handled_redis_key = packet_handled_redis_key(packet_id, 
                                                            for_client=packet.client_id)
                # Want to make sure not to handle the same packet twice due to a re-send, 
                # if our ack didn't get through
                if not rget(handled_redis_key, client_id=None):
                    self.handle_payload_from_client(payload, packet)
                    send_ack(conn, packet_id)
                    rset(handled_redis_key, '1', client_id=None)
                else:
                    print(f'Ignoring {packet} because this packet has already been handled')

    def handle_data_from_client(self, raw_data: str, conn: Any) -> None:
        for datum in raw_data.split(';'):
            if datum:
                global stored_data
                # Sometimes packets get split by TCP or something, 
                # so if we fail to process a packet successfully, we store it and instead try processing it concatenated
                # to the next packet
                try:
                    self._handle_datum(conn, datum)
                except Exception as e1:
                    stored_data.append(datum)
                    if len(stored_data) > 1:
                        joint_datum = ''.join(stored_data)
                        try:
                            self._handle_datum(conn, ''.join(stored_data))
                        except Exception as e2:
                            print(f'Ignoring {joint_datum[:LOG_CUTOFF]} because of exception: {e2}')
                        else:
                            _clear_stored_data(stored_data)
                    else:
                        print(f'Ignoring {datum[:LOG_CUTOFF]} because of exception: {e1}')
                else:
                    _clear_stored_data(stored_data)


def _get_new_connection_id(active_connections_by_id: dict[int, Connection]) -> int:
    if active_connections_by_id:
        return max(active_connections_by_id.keys()) + 1
    return 1


def _handle_incoming_connection(connection: Connection, game_state: GameState) -> None:
    print('handling incoming connection!')
    while True:
        data = connection.conn.recv(1048576).decode()
        game_state.handle_data_from_client(data, connection.conn)


def _handle_outgoing_active_players_connection(connection: Connection) -> None:
    def _handle_change(channel: str, value: Optional[str]) -> None:
        send_without_retry(connection.conn, f'{channel}|{value}', client_id=None)

    rlisten(_SUBSCRIPTION_KEYS, _handle_change)


def _create_game_state_snaps() -> None:
    while True:
        game.infer_and_store_game_state_snap()

        sleep(SNAPSHOTS_CREATED_EVERY)


    # while True:
    #     active_players = game_state.get_active_players()
    #     players_list = rget('active_players', client_id=None)
    #     send_without_retry(connection.conn, f'active_players|{json.dumps(players_list)}', client_id=None)
    #     for p in active_players:
    #         player_state = game_state.get_player_state(p)
    #         if player_state is not None:
    #             send_without_retry(connection.conn, f'player_state_{p}|{player_state}', client_id=None)
    #         sleep(1)
    #     sleep(1)


def main() -> None:
    flushall()
    active_connections_by_id: dict[int, Connection] = {}

    game_state = GameState()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    start_new_thread(_create_game_state_snaps, tuple([]))
    try:
        s.bind((socket.gethostbyname(socket.gethostname()), PORT))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.listen()
        print('Starting the server!')
        while True:
            print('Waiting on a new connection...')
            conn, addr = s.accept()
            print('New connection!')
            new_connection_id = _get_new_connection_id(active_connections_by_id)
            connection = Connection(new_connection_id, conn, addr)
            active_connections_by_id[new_connection_id] = connection
            game_state.set_active_players(active_connections_by_id)
            
            sleep(0.01)
            print(f'A new client has connected! ID: {new_connection_id}')
            start_new_thread(send_with_retry, (conn, f'client_id|{new_connection_id}', None))
            print(f'Done sending client id of {new_connection_id}!')
            sleep(0.001)

            start_new_thread(_handle_incoming_connection, (connection, game_state))
            start_new_thread(_handle_outgoing_active_players_connection, (connection,))

            print(f'New connection: {connection}')
    except BaseException as e:
        print(f'Error: {e}. Closing the socket')
        s.close()


if __name__ == '__main__':
    main()