from datetime import datetime, timedelta
import json
import zlib
from team import get_team_for_client_id
from utils import SNAPSHOTS_CREATED_EVERY, LOG_CUTOFF, SPECIAL_LOBBY_MANAGER_GAME_NAME, GAME_HEIGHT, GAME_WIDTH
from command import Command, store_command, CommandType
from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock, flushall, rlisten
import gevent
from _thread import start_new_thread
from time import sleep
from packet import (
    Packet, send_with_retry, send_without_retry, send_ack, packet_ack_redis_key, 
    packet_handled_redis_key, send_with_retry_on_delay
)
import game
import random
from team import Team
import traceback


_SUBSCRIPTION_KEYS = ['active_players', 
                      'most_recent_game_state_snapshot',
                      'commands_by_player',
                      'commands_by_projectile',
                      'client_id_to_player_number',
                      'client_id_to_team',
                      'game_started']


_LOBBY_MANAGER_SUBSCRIPTION_KEYS = ['game_names']

_GAME_NAMES_LOCK_REDIS_KEY = 'game_names_lock_redis_key'


active_connections_by_client_id_and_game_name: set[tuple[int, str]] = set()
client_ids_to_game_name: dict[int, str] = {}


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


# Returns a dict from game name to whether or not that game has started
def _get_game_names() -> dict[str, bool]:
    return json.loads(rget('game_names', client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME) or '{}')


class GameState:
    def set_active_players(self, active_connections_by_id: dict, game_name: str):
        client_ids = active_connections_by_id.keys()
        rset('active_players', ','.join(str(i) for i in client_ids), client_id=None, game_name=game_name)

    def get_active_players(self, game_name: str) -> list[int]:
        active_players = rget('active_players', client_id=None, game_name=game_name) or ''
        return [int(i) for i in active_players.split(',')]

    def handle_payload_from_client(self, connection: Connection, payload: str, packet: Packet, game_name: str):
        
        # Only the lobby manager should care about these packets

        if (payload.startswith('join_game') and game_name == SPECIAL_LOBBY_MANAGER_GAME_NAME):
            with redis_lock(_GAME_NAMES_LOCK_REDIS_KEY, client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME):
                _, player_name, game_to_join_name = payload.split('|')
                assert packet.client_id
                connection_tup = (packet.client_id, game_to_join_name)
                if connection_tup not in active_connections_by_client_id_and_game_name and game_to_join_name in _get_game_names():
                    players_in_game = json.loads(rget(f'active_players', client_id=None, game_name=game_to_join_name) or '[]')
                    players_in_game.append([player_name, packet.client_id])
                    active_connections_by_client_id_and_game_name.add(connection_tup)
                    client_ids_to_game_name[packet.client_id] = game_to_join_name
                    start_new_thread(_handle_incoming_connection, (connection, self, game_to_join_name, packet.client_id))
                    start_new_thread(_handle_outgoing_active_players_connection, (connection, game_to_join_name, packet.client_id))       
                    sleep(0.02)     
                    rset(f'active_players', json.dumps(players_in_game), client_id=None, game_name=game_to_join_name)

        elif payload.startswith('leave_game') and game_name == SPECIAL_LOBBY_MANAGER_GAME_NAME:
            with redis_lock(_GAME_NAMES_LOCK_REDIS_KEY, client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME):
                _, player_name, game_to_leave_name = payload.split('|')
                assert packet.client_id
                connection_tup = (packet.client_id, game_to_leave_name)
                if connection_tup in active_connections_by_client_id_and_game_name:
                    players_in_game = json.loads(rget(f'active_players', client_id=None, game_name=game_to_leave_name) or '[]')
                    for i, player_info in enumerate(players_in_game):
                        if player_info[0] == player_name and player_info[1] == packet.client_id:
                            del players_in_game[i]
                            break
                    assert packet.client_id
                    active_connections_by_client_id_and_game_name.remove(connection_tup)
                    client_ids_to_game_name[packet.client_id] = SPECIAL_LOBBY_MANAGER_GAME_NAME
                    sleep(0.02)
                    rset(f'active_players', json.dumps(players_in_game), client_id=None, game_name=game_to_leave_name)      

        elif payload.startswith('host_game') and game_name == SPECIAL_LOBBY_MANAGER_GAME_NAME:
            with redis_lock(_GAME_NAMES_LOCK_REDIS_KEY, client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME):
                _, player_name, game_to_host_name = payload.split('|')
                assert packet.client_id
                connection_tup = (packet.client_id, game_to_host_name)
                all_game_names = _get_game_names()
                if (connection_tup not in active_connections_by_client_id_and_game_name 
                        and game_to_host_name not in all_game_names):
                    active_connections_by_client_id_and_game_name.add(connection_tup)
                    client_ids_to_game_name[packet.client_id] = game_to_host_name
                    start_new_thread(_handle_incoming_connection, (connection, self, game_to_host_name, packet.client_id))
                    start_new_thread(_handle_outgoing_active_players_connection, (connection, game_to_host_name, packet.client_id))
                    all_game_names[game_to_host_name] = False
                    sleep(0.02)
                    rset('game_names', json.dumps(all_game_names), client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME)
                    rset(f'active_players', json.dumps([[player_name, packet.client_id]]), client_id=None, game_name=game_to_host_name)

        # End "Only the lobby manager should care about these packets"

        elif payload.startswith('start_game') and game_name != SPECIAL_LOBBY_MANAGER_GAME_NAME:
            with redis_lock(_GAME_NAMES_LOCK_REDIS_KEY, client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME):
                all_game_names = _get_game_names()
                if not all_game_names[game_name]:
                    all_game_names[game_name] = True
                    
                    players_in_game = json.loads(rget('active_players', client_id=None, game_name=game_name) or '[]')
                    for i in range(max(8 - len(players_in_game), 0)):
                        # These will eventually be the AI players
                        players_in_game.append(['', 10000 + i])

                    print(players_in_game)
                    print(f'game name: {game_name}')     
                    client_ids_in_game = [player_info[1] for player_info in players_in_game]
                    random.shuffle(client_ids_in_game)
                    client_id_to_team: dict[int, Team] = {}
                    client_id_to_player_number: dict[int, int] = {}
                    red_team = random.sample(client_ids_in_game, 4)
                    for i, client_id in enumerate(client_ids_in_game):
                        if client_id in red_team:
                            client_id_to_team[client_id] = Team.RED
                        else:
                            client_id_to_team[client_id] = Team.BLUE
                        player_number = i + 1
                        client_id_to_player_number[client_id] = player_number
                        rset(f'player_number:{client_id}', player_number, client_id=None, game_name=game_name)
                        rset(f'client_id:{player_number}', client_id, client_id=None, game_name=game_name)

                    sleep(0.1)
                    rset('client_id_to_team', json.dumps({k: v.value for k, v in client_id_to_team.items()}), client_id=None, game_name=game_name)
                    sleep(0.1)
                    rset('client_id_to_player_number', json.dumps(client_id_to_player_number), client_id=None, game_name=game_name)
                    sleep(0.1)
                    rset('game_started', '1', client_id=None, game_name=game_name)
                    sleep(0.1)
                    rset('game_names', json.dumps(all_game_names), client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME)

                    for i, client_id in enumerate(client_ids_in_game):
                        store_command(Command(1, CommandType.SPAWN, time=datetime.now() - timedelta(seconds=5), client_id=client_id, 
                                    data={'x': random.randint(1, GAME_WIDTH), 
                                            'y': random.randint(1, GAME_HEIGHT),
                                            'team': client_id_to_team[client_id].value}), for_client=client_id, client_id=None, game_name=game_name)
                        sleep(0.1)                                            
                    start_new_thread(_create_game_state_snaps, (game_name,))

        elif payload.startswith('command') and game_name != SPECIAL_LOBBY_MANAGER_GAME_NAME:
            all_game_names = _get_game_names()
            if all_game_names[game_name]:
                _, data = payload.split('|')
                assert packet.client_id is not None
                store_command(Command.from_json(json.loads(data)), client_id=None, for_client=packet.client_id, game_name=game_name)
            
    def _handle_datum(self, connection: Connection, datum: str, game_name: str) -> None:
        print(f'received: {datum[:LOG_CUTOFF]}\n')
        packet = Packet.from_str(datum)
        packet_id = packet.id
        payload = packet.payload
        if packet.is_ack:
            assert packet_id is not None
            # Record in redis that the message has been acked
            print(f'Received ack for {packet}')
            rset(packet_ack_redis_key(packet_id), '1', client_id=None, game_name=game_name)
        elif packet_id is None:
            assert payload is not None
            self.handle_payload_from_client(connection, payload, packet, game_name=game_name)
        else:
            assert payload is not None
            with redis_lock(f'handle_payload_from_client|{packet.client_id}|{packet.id}', 
                            client_id=None, game_name=game_name):
                handled_redis_key = packet_handled_redis_key(packet_id, 
                                                            for_client=packet.client_id)
                # Want to make sure not to handle the same packet twice due to a re-send, 
                # if our ack didn't get through
                if not rget(handled_redis_key, client_id=None, game_name=game_name):
                    self.handle_payload_from_client(connection, payload, packet, game_name=game_name)
                    send_ack(connection.conn, packet_id)
                    rset(handled_redis_key, '1', client_id=None, game_name=game_name)
                else:
                    print(f'Ignoring {packet} because this packet has already been handled')

    def handle_data_from_client(self, raw_data: str, connection: Connection, game_name: str) -> None:
        for datum in raw_data.split(';'):
            if datum:
                global stored_data
                # Sometimes packets get split by TCP or something, 
                # so if we fail to process a packet successfully, we store it and instead try processing it concatenated
                # to the next packet
                try:
                    self._handle_datum(connection, datum, game_name=game_name)
                except Exception as e1:
                    stored_data.append(datum)
                    if len(stored_data) > 1:
                        joint_datum = ''.join(stored_data)
                        try:
                            self._handle_datum(connection, ''.join(stored_data), game_name=game_name)
                        except Exception as e2:
                            print(f'Ignoring {joint_datum[:LOG_CUTOFF]} because of exception: {e2}')
                            traceback.print_exc()
                        else:
                            _clear_stored_data(stored_data)
                    else:
                        print(f'Ignoring {datum[:LOG_CUTOFF]} because of exception: {e1}')
                        traceback.print_exc()
                else:
                    _clear_stored_data(stored_data)


def _get_new_connection_id(active_connections_by_id: dict[int, Connection]) -> int:
    if active_connections_by_id:
        return max(active_connections_by_id.keys()) + 1
    return 101


def _handle_incoming_connection(connection: Connection, game_state: GameState, game_name: str, for_client_id: int) -> None:
    print(f'handling incoming connection! ({for_client_id, game_name})')
    while True:
        try:
            data = zlib.decompress(connection.conn.recv(1048576)).decode()
        except Exception as e:
            print(f'Error decompressing data: {e}')
            data = ''
            sleep(0.02)            
        game_state.handle_data_from_client(data, connection, game_name=game_name)

        if game_name != SPECIAL_LOBBY_MANAGER_GAME_NAME and (for_client_id, game_name) not in active_connections_by_client_id_and_game_name:
            print(f'breaking connection: ({for_client_id, game_name})')
            break


def _handle_outgoing_active_players_connection(connection: Connection, game_name: str, for_client_id: int) -> None:
    def _handle_change(channel: str, value: Optional[str]) -> None:
        print(f'Broadcasting: {channel}|{value} to {game_name}')
        send_without_retry(connection.conn, f'{channel}|{value}', client_id=None)
    
    def _break_when() -> bool:
        if (for_client_id, game_name) not in active_connections_by_client_id_and_game_name:
            return True
        return False

    subscription_keys = _SUBSCRIPTION_KEYS if game_name != SPECIAL_LOBBY_MANAGER_GAME_NAME else _LOBBY_MANAGER_SUBSCRIPTION_KEYS
    rlisten(subscription_keys, _handle_change, game_name=game_name, break_when=_break_when if game_name != SPECIAL_LOBBY_MANAGER_GAME_NAME else None)


def _create_game_state_snaps(game_name: str) -> None:
    if game_name == SPECIAL_LOBBY_MANAGER_GAME_NAME:
        return
    while True:
        game.infer_and_store_game_state_snap(game_name)

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


def server_loop(game_name: str) -> None:
    flushall()
    active_connections_by_id: dict[int, Connection] = {}

    game_state = GameState()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    start_new_thread(_create_game_state_snaps, (game_name,))
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
            game_state.set_active_players(active_connections_by_id, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME)
            
            sleep(0.01)
            print(f'A new client has connected! ID: {new_connection_id}')
            start_new_thread(send_with_retry, (conn, f'client_id|{new_connection_id}', None, SPECIAL_LOBBY_MANAGER_GAME_NAME))
            start_new_thread(send_with_retry_on_delay, (conn, 0.25, f'game_names|{rget("game_names", client_id=None, game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME) or "{}"}', None, SPECIAL_LOBBY_MANAGER_GAME_NAME))
            print(f'Done sending client id of {new_connection_id}!')
            sleep(0.001)

            start_new_thread(_handle_incoming_connection, (connection, game_state, SPECIAL_LOBBY_MANAGER_GAME_NAME, new_connection_id))
            start_new_thread(_handle_outgoing_active_players_connection, (connection, SPECIAL_LOBBY_MANAGER_GAME_NAME, new_connection_id))

            print(f'New connection: {connection}')
    except BaseException as e:
        print(f'Error: {e}. Closing the socket')
        s.close()


if __name__ == '__main__':
    server_loop(game_name=SPECIAL_LOBBY_MANAGER_GAME_NAME)