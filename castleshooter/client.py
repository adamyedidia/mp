from datetime import datetime, timedelta
from command import Command, get_commands_by_player, commands_by_player
import game
from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock    
from _thread import start_new_thread
from threading import Thread
from client_utils import client
from packet import (
    Packet, send_ack, send_spawn_command, send_without_retry, packet_ack_redis_key, packet_handled_redis_key
)
import json
from json.decoder import JSONDecodeError
from game import GameState, game_state_snapshots
from utils import MAX_GAME_STATE_SNAPSHOTS, SNAPSHOTS_CREATED_EVERY, LOG_CUTOFF
from time import sleep


def start_up_game(socket: Any) -> None:
    print('starting up game!')
    assert client.id is not None
    sleep(0.5)
    print('Sending the spawn command!')
    send_spawn_command(socket, 50, 50, client_id=client.id)    
    g = game.Game(500,500, client, socket)
    g.run()    


def _handle_client_id_packet(payload: str) -> bool:
    if payload.startswith('client_id|') and client.id in [None, -1]:
        _, raw_client_id = payload.split('|')
        print(f'setting client id to {raw_client_id}')
        client.set_id(int(raw_client_id))
        return True
    return False    


def _handle_payload_from_server(payload: str) -> None:
    if payload.startswith('client_id|') and client.id is None:
        pass
    else:
        key, data = payload.split('|')

        if 'most_recent_game_state_snapshot' in key:
            try:
                json.loads(data)
            except JSONDecodeError as e:
                print(f'Ignoring unparseable snap from server: {data[:LOG_CUTOFF]}')
                return
            game_state_snapshots.append(data)
            if len(game_state_snapshots) > MAX_GAME_STATE_SNAPSHOTS:
                del game_state_snapshots[0]

        if 'commands_by_player' in key:
            raw_commands_by_player = get_commands_by_player(client_id=client.id)
            raw_commands_by_player_from_server = {int(key): val for key, val in json.loads(data).items()}
            player_ids_handled: set[int] = set()
            global commands_by_player
            for player_id, raw_commands in raw_commands_by_player.items():
                player_ids_handled.add(player_id)
                commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands], 
                                             key=lambda c: c.time)
                commands_for_player = [c for c in commands_for_player 
                                       if c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)]
                raw_commands_from_server = raw_commands_by_player_from_server.get(player_id) or []
                commands_for_player_from_server = sorted([Command.from_json(json.loads(c)) for c in raw_commands_from_server], key=lambda c: c.time)
                commands_for_player_from_server = [c for c in commands_for_player_from_server 
                                                  if (c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)
                                                      and c.id not in [ci.id for ci in commands_for_player])]
                commands_for_player.extend(commands_for_player_from_server)
                commands_by_player[player_id] = [json.dumps(c.to_json()) for c in commands_for_player]

            for player_id, raw_commands_from_server in raw_commands_by_player_from_server.items():
                if player_id in player_ids_handled:
                    continue
                player_ids_handled.add(player_id)
                commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands_from_server], 
                                             key=lambda c: c.time)                
                commands_for_player = [c for c in commands_for_player 
                                       if c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)]
                commands_by_player[player_id] = [json.dumps(c.to_json()) for c in commands_for_player]                                             


stored_data: list[str] = []


def _clear_stored_data(stored_data: list[str]) -> None:
    while stored_data:
        del stored_data[0]


# Returns whether or not it's the client_id packet at the beginning
def _handle_datum(socket: Any, datum: str, client_id_only: bool = False) -> bool:
    print(f'received: {datum[:LOG_CUTOFF]}\n')
    packet = Packet.from_str(datum)
    packet_id = packet.id
    payload = packet.payload
    if packet.is_ack:
        assert packet_id is not None
        # Record in redis that the message has been acked
        rset(packet_ack_redis_key(packet_id), '1', client_id=client.id)
    elif packet_id is None:
        assert payload is not None
        _handle_payload_from_server(payload)
    else:
        assert payload is not None
        handled_redis_key = packet_handled_redis_key(packet_id, for_client=None)
        # Want to make sure not to handle the same packet twice due to a re-send, 
        # if our ack didn't get through
        if not rget(handled_redis_key, client_id=client.id or -1):
            if client_id_only:
                if _handle_client_id_packet(payload):
                    return True
            else:
                _handle_payload_from_server(payload)
            send_ack(socket, packet_id)
            rset(handled_redis_key, '1', client_id=client.id or -1)
        else:
            print(f'Ignoring {packet[:LOG_CUTOFF]} because this packet has already been handled\n')
    return False


def listen_for_server_updates(socket: Any, client_id_only: bool = False) -> None:
    while True:
        global stored_data
        raw_data = socket.recv(1048576).decode()
        for datum in raw_data.split(';'):
            # Sometimes packets get split by TCP or something, 
            # so if we fail to process a packet successfully, we store it and instead try processing it concatenated
            # to the next packet            
            if datum:
                try:
                    if _handle_datum(socket, datum, client_id_only=client_id_only) and client_id_only:
                        return
                except Exception as e1:
                    stored_data.append(datum)
                    if len(stored_data) > 1:
                        joint_datum = ''.join(stored_data)
                        try:
                            if _handle_datum(socket, ''.join(stored_data), client_id_only=client_id_only) and client_id_only:
                                return
                        except Exception as e2:
                            print(f'Ignoring {joint_datum} because of exception: {e2}\n')
                        else:
                            _clear_stored_data(stored_data)
                    else:
                        print(f'Ignoring {datum} because of exception: {e1}\n')
                else:
                    _clear_stored_data(stored_data)


def client_main() -> None:

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER, PORT))
        print('connected to server!')

        print('initialized game!')
        thread = Thread(target=listen_for_server_updates, args=(s,True))
        thread.start()
        print('Listening for server updates!')
        thread.join()
        start_new_thread(listen_for_server_updates, (s,))
        start_up_game(s)
    finally:
        print('Closing the socket!!')
        s.close()

if __name__ == '__main__':
    client_main()