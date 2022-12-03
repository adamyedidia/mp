from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
import gevent
from settings import TEST_LAG
from direction import Direction
from command import Command, CommandType, store_command
from redis_utils import redis_lock, rget, rset, rlisten
from utils import to_optional_int
from time import sleep
import json


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


def _generate_next_packet_id(client_id: Optional[int]) -> int:
    with redis_lock('generate_next_packet_id_redis_lock', client_id=client_id):
        next_packet_id = int(rget('last_packet_id', client_id=client_id) or '0') + 1
        rset('last_packet_id', next_packet_id, client_id=client_id)
    return next_packet_id


def packet_ack_redis_key(packet_id: int) -> str:
    return f'packet_ack|{packet_id}'


def packet_handled_redis_key(packet_id: int, *, for_client: Optional[int]) -> str:
    for_client_suffix = f'|{for_client}' if for_client is not None else ''
    return f'packet_handled|{packet_id}{for_client_suffix}'


# Returns the boolean of whether or not the message was successfully sent (i.e. an ack was received)
def _send_with_retry_inner(conn: Any, packet: Packet, wait_time: float, *, 
                           client_id: Optional[int]) -> bool:
    packet_id = packet.id
    assert packet_id is not None
    # print(f'Sending {packet}')
    conn.sendall(bytes(packet.to_str(), 'utf-8'))
    sleep(wait_time)

    # We're relying on a different process to listen for acks and write to redis when one is seen
    ack_redis_key = packet_ack_redis_key(packet_id)
    if rget(ack_redis_key, client_id=client_id):
        return True
    return False


# Returns the boolean of whether or not the message was successfully sent (i.e. an ack was received)
def send_with_retry(conn: Any, message: str, client_id: Optional[int]) -> bool:
    packet_id = _generate_next_packet_id(client_id=client_id)
    packet = Packet(id=packet_id, client_id=client_id, payload=message)
    wait_times = [0.05, 0.1, 0.2, 0.4, 0.8]
    for i, wait_time in enumerate(wait_times):
        if _send_with_retry_inner(conn, packet, wait_time, client_id=client_id):
            return True
        # debug_msg = f'Did not get a response in {wait_time} for {packet}'
        # if i < len(wait_times) - 1:
        #     debug_msg = f'{debug_msg}, retrying...'
        # print(debug_msg)
    return False


def send_without_retry(conn: Any, message: str, *, client_id: Optional[int]) -> None:
    if TEST_LAG > 0:
        sleep(TEST_LAG)
    packet = Packet(client_id=client_id, payload=message)
    print(f'Sending without retry {packet}')    
    conn.sendall(bytes(packet.to_str(), 'utf-8'))


def send_ack(conn: Any, packet_id: int) -> None:
    packet = Packet(id=packet_id, is_ack=True)
    # print(f'Acking {packet}')        
    conn.sendall(bytes(packet.to_str(), 'utf-8'))    


def send_command(conn: Any, command: Command, *, client_id: int) -> None:
    store_command(command, for_client=client_id, client_id=client_id)
    send_without_retry(conn, f'command|{json.dumps(command.to_json())}', client_id=client_id)


def _generate_next_command_id(client_id: Optional[int]) -> int:
    next_command_id = int(rget('next_command_id', client_id=client_id) or '0') + 1
    rset('next_command_id', next_command_id, client_id=client_id)
    return next_command_id

def send_move_command(conn: Any, x_pos: int, y_pos: int, *, client_id: int) -> None:
    send_command(conn, Command(id=_generate_next_command_id(client_id=client_id), 
                        type=CommandType.MOVE, time=datetime.now(), client_id=client_id, 
                        data={'x': x_pos, 'y': y_pos}), client_id=client_id)


def send_spawn_command(conn: Any, x_pos: int, y_pos: int, *, client_id: int) -> None:
    send_command(conn, Command(id=_generate_next_command_id(client_id=client_id), 
                        type=CommandType.SPAWN, time=datetime.now(), client_id=client_id, 
                        data={'x': x_pos, 'y': y_pos}), client_id=client_id)


def send_turn_command(conn: Any, direction: Optional[Direction], *, client_id: int) -> None:
    send_command(conn, Command(id=_generate_next_command_id(client_id=client_id),
                 type=CommandType.TURN, time=datetime.now(), client_id=client_id, 
                 data={'dir': direction.value if direction else None}),
                 client_id=client_id)