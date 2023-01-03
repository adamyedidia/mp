from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
import random
from typing import Any, Optional
import zlib
import gevent
from team import Team
from death_reason import DeathReason
from projectile import ProjectileType
from settings import TEST_LAG, DROP_CHANCE
from direction import Direction
from command import Command, CommandType, store_command
from redis_utils import redis_lock, rget, rset, rlisten
from utils import to_optional_int
from time import sleep
import json
from _thread import start_new_thread


class Packet:
    # Packets with a None id do not need an ack
    def __init__(self, *, id: Optional[int] = None, 
                 client_id: Optional[int] = None, 
                 is_ack: bool = False, 
                 payload: Optional[str] = None) -> None:
        if payload is not None:
            assert ';' not in payload
            assert '||' not in payload
        self.id = id
        self.client_id = client_id
        self.is_ack = is_ack
        self.payload = payload
    
    def to_str(self):
        if self.is_ack:
            return f'@{self.id};'
        else:
            if self.id is None:
                return f'~||{self.client_id}||{self.payload};'
            else:
                return f'{self.id}||{self.client_id}||{self.payload};'

    @classmethod
    def from_str(cls, packet_str: str) -> 'Packet':
        if packet_str.startswith('@'):
            return Packet(is_ack=True, id=int(packet_str[1:]))
        elif packet_str.startswith('~'):
            _, client_id, payload = packet_str.split('||')
            return Packet(client_id=to_optional_int(client_id), payload=payload)
        else:
            packet_id, client_id, payload = packet_str.split('||')
            return Packet(id=int(packet_id), client_id=to_optional_int(client_id), payload=payload)

    def __repr__(self) -> str:
        return f'<Packet {self.id}: {self.to_str()}>'


def _generate_next_packet_id(client_id: Optional[int], game_name: Optional[str] = None) -> int:
    with redis_lock('generate_next_packet_id_redis_lock', client_id=client_id, game_name=game_name) if client_id is None else nullcontext():
        next_packet_id = int(rget('last_packet_id', client_id=client_id, game_name=game_name) or '0') + 1
        rset('last_packet_id', next_packet_id, client_id=client_id, game_name=game_name)
    return next_packet_id


def packet_ack_redis_key(packet_id: int) -> str:
    return f'packet_ack|{packet_id}'


def packet_handled_redis_key(packet_id: int, *, for_client: Optional[int]) -> str:
    for_client_suffix = f'|{for_client}' if for_client is not None else ''
    return f'packet_handled|{packet_id}{for_client_suffix}'


def receive_compressed_message(socket: Any) -> str:
    try:
        prepreamble = socket.recv(1).decode()
    except UnicodeDecodeError:
        return ''
    if prepreamble != '[':
        return ''
    try:
        preamble = socket.recv(11).decode()
    except UnicodeDecodeError:
        return ''
    if preamble[:3] != '[[[':
        return ''
    
    total_length_of_message = int(preamble[3:])
    length_read_so_far = 0
    chunk_size = 256
    messages: list[bytes] = []
    print(total_length_of_message)
    while length_read_so_far < total_length_of_message:
        next_chunk_length = max(min(chunk_size, total_length_of_message - length_read_so_far), 0)
        messages.append(socket.recv(next_chunk_length))
        length_read_so_far += next_chunk_length
    
    socket.recv(4)
    
    return zlib.decompress(b''.join(messages)).decode()


def _send_compressed_message(conn: Any, compressed_message: bytes) -> None:
    print(len(compressed_message))
    conn.sendall(b'[[[[' + bytes(f"{len(compressed_message):08}", 'utf-8') + compressed_message + b']]]]')


# Returns the boolean of whether or not the message was successfully sent (i.e. an ack was received)
def _send_with_retry_inner(conn: Any, packet: Packet, wait_time: float, *, 
                           client_id: Optional[int], game_name: Optional[str] = None) -> bool:
    packet_id = packet.id
    assert packet_id is not None
    # print(f'Sending {packet}')
    if DROP_CHANCE and random.random() < DROP_CHANCE:
        return False    
    _send_compressed_message(conn, zlib.compress(bytes(packet.to_str(), 'utf-8')))

    sleep(wait_time)

    # We're relying on a different process to listen for acks and write to redis when one is seen
    ack_redis_key = packet_ack_redis_key(packet_id)
    if rget(ack_redis_key, client_id=client_id, game_name=game_name):
        return True
    return False


# Returns the boolean of whether or not the message was successfully sent (i.e. an ack was received)
def send_with_retry(conn: Any, message: str, client_id: Optional[int], game_name: Optional[str] = None) -> bool:
    if TEST_LAG:
        sleep(TEST_LAG)
    packet_id = _generate_next_packet_id(client_id=client_id, game_name=game_name)
    packet = Packet(id=packet_id, client_id=client_id, payload=message)
    wait_times = [0.2, 0.4, 0.8]
    for i, wait_time in enumerate(wait_times):
        if _send_with_retry_inner(conn, packet, wait_time, client_id=client_id, game_name=game_name):
            return True
        # debug_msg = f'Did not get a response in {wait_time} for {packet}'
        # if i < len(wait_times) - 1:
        #     debug_msg = f'{debug_msg}, retrying...'
        # print(debug_msg)
    return False


def send_with_retry_on_delay(conn: Any, delay: float, message: str, client_id: Optional[int], game_name: Optional[str] = None) -> bool:
    sleep(delay)
    return send_with_retry(conn, message, client_id, game_name=game_name)


def send_with_test_lag(conn: Any, message: str, lag: float, *, client_id: Optional[int]) -> None:
    sleep(lag)
    packet = Packet(client_id=client_id, payload=message)
    # print(f'Sending without retry {packet}')    
    conn.sendall(zlib.compress(bytes(packet.to_str(), 'utf-8')))

def send_without_retry(conn: Any, message: str, *, client_id: Optional[int]) -> None:
    if DROP_CHANCE and random.random() < DROP_CHANCE:
        return        
    if TEST_LAG:
        start_new_thread(send_with_test_lag, (conn, message, TEST_LAG), {'client_id': client_id})
    else:
        packet = Packet(client_id=client_id, payload=message)
        # print(f'Sending without retry {packet}')    
        _send_compressed_message(conn, zlib.compress(bytes(packet.to_str(), 'utf-8')))


def send_ack(conn: Any, packet_id: int) -> None:
    packet = Packet(id=packet_id, is_ack=True)
    # print(f'Acking {packet}')
    _send_compressed_message(conn, zlib.compress(bytes(packet.to_str(), 'utf-8')))


# game_name only used by AI players
def send_command(conn: Any, command: Command, *, client_id: int, game_name: Optional[str] = None) -> Command:
    if conn is not None:
        store_command(command, for_client=client_id, client_id=client_id)
        command_str = f'command|{json.dumps(command.to_json())}'
        print(f'Sending command: {command_str}\n')
        start_new_thread(send_with_retry, (conn, f'command|{json.dumps(command.to_json())}', client_id))
    else:
        # AI players are run directly on the server and so have direct access to the server db
        store_command(command=command, for_client=client_id, client_id=None, game_name=game_name)

    return command


def _generate_next_command_id(client_id: Optional[int]) -> int:
    next_command_id = int(rget('next_command_id', client_id=client_id) or '0') + 2
    rset('next_command_id', next_command_id, client_id=client_id)
    return next_command_id


# game_name only used by AI players
def send_move_command(conn: Any, x_pos: int, y_pos: int, *, client_id: int, game_name: Optional[str] = None) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id), 
                        type=CommandType.MOVE, time=datetime.now(), client_id=client_id, 
                        data={'x': x_pos, 'y': y_pos}), client_id=client_id, game_name=game_name)


def generate_spawn_command(x_pos: int, y_pos: int, team: Team, *, client_id: int) -> Command:
    return Command(id=_generate_next_command_id(client_id=client_id), 
                   type=CommandType.SPAWN, time=datetime.now(), client_id=client_id, 
                   data={'x': x_pos, 'y': y_pos, 'team': team.value})


def send_spawn_command(conn: Any, x_pos: int, y_pos: int, team: Team, *, client_id: int) -> Command:
    return send_command(conn, generate_spawn_command(x_pos, y_pos, team, client_id=client_id), client_id=client_id)


def send_turn_command(conn: Any, direction: Optional[Direction], *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                 type=CommandType.TURN, time=datetime.now(), client_id=client_id, 
                 data={'dir': direction.value if direction else None}),
                 client_id=client_id)


def send_spawn_projectile_command(conn: Any, projectile_id: int, source_x: int, source_y: int, dest_x: int, dest_y: int, 
                                  friends: list[int], type: ProjectileType, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                 type=CommandType.SPAWN_PROJECTILE, time=datetime.now(), client_id=client_id,
                 data={'id': projectile_id, 'source_x': source_x, 'source_y': source_y, 'dest_x': dest_x, 'dest_y': dest_y, 
                 'type': type.value, 'player_id': client_id, 'friends': friends}), client_id=client_id)


def send_eat_arrow_command(conn: Any, arrow_start_x: int, arrow_start_y: int, arrow_end_x: int, arrow_end_y: int, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                 type=CommandType.EAT_ARROW, time=datetime.now(), client_id=client_id,
                 data={'arrow_start_x': arrow_start_x, 'arrow_start_y': arrow_start_y, 'arrow_end_x': arrow_end_x, 
                 'arrow_end_y': arrow_end_y, 'player_id': client_id}), client_id=client_id)


def send_remove_projectile_command(conn: Any, projectile_id: int, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                 type=CommandType.REMOVE_PROJECTILE, time=datetime.now(), client_id=client_id,
                 data={'projectile_id': projectile_id}), client_id=client_id)


def send_die_command(conn: Any, killer_id: int, verb: str, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                 type=CommandType.DIE, time=datetime.now(), data={'killer_id': killer_id, 'verb': verb}, 
                 client_id=client_id), client_id=client_id)


def send_lose_hp_command(conn: Any, killer_id: int, victim_id: int, verb: str, hp: int, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                        type=CommandType.LOSE_HP, time=datetime.now(), 
                        data={'killer_id': killer_id, 'verb': verb, 'hp': hp}, client_id=victim_id), client_id=client_id)


def send_teleport_command(conn: Any, x: int, y: int, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                        type=CommandType.TELEPORT, time=datetime.now(), data={'x': x, 'y': y}, 
                        client_id=client_id), client_id=client_id)


def send_set_speed_command(conn: Any, speed: int, *, client_id: int) -> Command:
    return send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                        type=CommandType.SET_SPEED, time=datetime.now(), data={'speed': speed},
                        client_id=client_id), client_id=client_id)
