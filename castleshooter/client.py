from datetime import datetime, timedelta
import zlib
from announcement import Announcement, get_announcement_idempotency_key_for_command
from death_reason import DeathReason, death_reason_to_verb
from command import Command, CommandType, get_commands_by_player, commands_by_player, get_commands_by_projectile, commands_by_projectile
from settings import PORT, SERVER
import socket
from typing import Any, Optional
from redis_utils import rset, rget, redis_lock    
from _thread import start_new_thread
from threading import Thread
from client_utils import get_player_number_from_client_id
from client_utils import _client as client
from packet import (
    Packet, send_ack, send_spawn_command, send_without_retry, packet_ack_redis_key, packet_handled_redis_key, send_with_retry,
    receive_compressed_message
)
import json
from json.decoder import JSONDecodeError
from game import Game, GameState, game_state_snapshots, run_spontaneous_game_processes, handle_hp_loss_for_commands
from utils import MAX_GAME_STATE_SNAPSHOTS, SNAPSHOTS_CREATED_EVERY, LOG_CUTOFF, MAX_SCORE
from time import sleep
import pygame
from team import Team, flip_team
from score import score
import traceback


game: Optional[Game] = None


def get_game() -> Optional[Game]:
    global game
    return game


def start_up_game(socket: Any) -> None:
    print('starting up game!')
    assert client.id is not None
    sleep(0.5)
    print('Sending the spawn command!')  
    global game
    game = Game(750, 750, client, socket)
    start_new_thread(run_spontaneous_game_processes, (game,))
    start_new_thread(send_all_commands_heartbeats, (socket,))
    game.run()    


def _handle_client_id_packet(payload: str) -> bool:
    if payload.startswith('client_id|') and client.id in [None, -1]:
        _, raw_client_id = payload.split('|')
        print(f'setting client id to {raw_client_id}')
        client.set_id(int(raw_client_id))
        return True
    return False    


def handle_announcements_for_commands(commands_for_player: list[Command]) -> None:
    game = get_game()
    if game is not None:
        announcement_idempotency_keys = [a.idempotency_key for a in game.announcements]        
        for command in commands_for_player:
            command_idempotency_key = get_announcement_idempotency_key_for_command(command)
            if command_idempotency_key not in announcement_idempotency_keys:
                if command.type == CommandType.DIE:
                    assert command.data
                    assert command.client_id
                    verb = command.data['verb']
                    killer_id = int(command.data['killer_id'])
                    victim_id = get_player_number_from_client_id(command.client_id, client_id=client.id)
                    if victim_id == client.id:
                        message = f'Player {killer_id} {verb} you!'
                    elif killer_id == client.id:
                        message = f'You {verb} player {victim_id}!'
                    else:
                        message = f'Player {killer_id} {verb} player {victim_id}!'
                    game.add_announcement(Announcement(command_idempotency_key, datetime.now(), message))


def handle_client_changes_for_all_commands(commands_by_player: dict[int, list[str]]) -> None:
    game = get_game()
    if game is not None:
        for client_id, raw_commands in commands_by_player.items():
            for raw_command in raw_commands:
                command = Command.from_json(json.loads(raw_command))
                if command.id not in [c.id for c in game.commands_handled]:
                    if command.type == CommandType.DIE:
                        global score
                        actual_score = score.get()
                        actual_red_score, actual_blue_score = actual_score
                        game_over = actual_red_score >= MAX_SCORE or actual_blue_score >= MAX_SCORE
                        if not game_over:                    
                            team_to_gain_point = flip_team(Team(rget(f'team:{client_id}', client_id=client.id)))
                            score.increment(team_to_gain_point, max_delay_seconds=10)

                            game.commands_handled.append(command)
                            game.commands_handled = [c for c in game.commands_handled if c.time > datetime.now() - timedelta(seconds=20)]


def _handle_most_recent_game_snapshot(data: str) -> None:
    if not data:
        return
    try:
        json.loads(data)
    except JSONDecodeError as e:
        print(f'Ignoring unparseable snap from server: {data[:LOG_CUTOFF]}')
        return
    game_state_snapshots.append(data)
    if len(game_state_snapshots) > MAX_GAME_STATE_SNAPSHOTS:
        del game_state_snapshots[0]


def _handle_commands_by_player(data: str) -> None:
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
        handle_announcements_for_commands(commands_for_player)
        handle_hp_loss_for_commands(get_game(), commands_for_player)
        handle_client_changes_for_all_commands(commands_by_player)    

    for player_id, raw_commands_from_server in raw_commands_by_player_from_server.items():
        if player_id in player_ids_handled:
            continue
        player_ids_handled.add(player_id)
        commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands_from_server], 
                                        key=lambda c: c.time)                
        commands_for_player = [c for c in commands_for_player 
                                if c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)]
        commands_by_player[player_id] = [json.dumps(c.to_json()) for c in commands_for_player]     
        handle_announcements_for_commands(commands_for_player)   
        handle_hp_loss_for_commands(get_game(), commands_for_player)
        handle_client_changes_for_all_commands(commands_by_player)    


def _handle_commands_by_projectile(data: str) -> None:
    raw_commands_by_projectile = get_commands_by_projectile(client_id=client.id)
    raw_commands_by_projectile_from_server = {int(key): val for key, val in json.loads(data).items()}
    projectile_ids_handled: set[int] = set()
    global commands_by_projectile
    for projectile_id, raw_commands in raw_commands_by_projectile.items():
        projectile_ids_handled.add(projectile_id)
        commands_for_projectile = sorted([Command.from_json(json.loads(c)) for c in raw_commands], 
                                        key=lambda c: c.time)
        commands_for_projectile = [c for c in commands_for_projectile 
                                if c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)]
        raw_commands_from_server = raw_commands_by_projectile_from_server.get(projectile_id) or []
        commands_for_projectile_from_server = sorted([Command.from_json(json.loads(c)) for c in raw_commands_from_server], key=lambda c: c.time)
        commands_for_projectile_from_server = [c for c in commands_for_projectile_from_server 
                                            if (c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)
                                                and c.id not in [ci.id for ci in commands_for_projectile])]
        commands_for_projectile.extend(commands_for_projectile_from_server)
        commands_by_projectile[projectile_id] = [json.dumps(c.to_json()) for c in commands_for_projectile]

    for projectile_id, raw_commands_from_server in raw_commands_by_projectile_from_server.items():
        if projectile_id in projectile_ids_handled:
            continue
        projectile_ids_handled.add(projectile_id)
        commands_for_projectile = sorted([Command.from_json(json.loads(c)) for c in raw_commands_from_server], 
                                        key=lambda c: c.time)                
        commands_for_projectile = [c for c in commands_for_projectile 
                                if c.time > datetime.now() - timedelta(seconds=MAX_GAME_STATE_SNAPSHOTS*SNAPSHOTS_CREATED_EVERY)]
        commands_by_projectile[projectile_id] = [json.dumps(c.to_json()) for c in commands_for_projectile]       


def _handle_client_id_to_player_number(data: str) -> None:
    client_id_to_player_number = json.loads(data)

    for client_id, player_number in client_id_to_player_number.items():
        rset(f'player_number:{client_id}', player_number, client_id=client.id)
        rset(f'client_id:{player_number}', client_id, client_id=client.id)

    start_new_thread(_start_game_on_delay, tuple([]))    


def _handle_client_id_to_team(data: str) -> None:
    client_id_to_team = json.loads(data)
    for client_id, team in client_id_to_team.items():
        rset(f'team:{client_id}', team, client_id=client.id)
        if int(client_id) == int(client.id):
            print(f'Setting team to {team}')
            client.set_team(Team(team))


def _handle_payload_from_server(payload: str) -> None:
    if payload.startswith('client_id|') and client.id is None:
        pass
    else:
        key, data = payload.split('|')

        if 'most_recent_game_state_snapshot' in key:
            _handle_most_recent_game_snapshot(data)

        if 'commands_by_player' in key:
            _handle_commands_by_player(data)

        if 'commands_by_projectile' in key:
            _handle_commands_by_projectile(data)

        if 'client_id_to_player_number' in key:
            _handle_client_id_to_player_number(data)

        if 'client_id_to_team' in key:
            _handle_client_id_to_team(data)

        if 'active_players' in key:
            rset('active_players', data, client_id=client.id)

        if 'game_names' in key:
            print(f'Setting game_names to {data}')
            rset('game_names', data, client_id=client.id)

        if 'all_info_digest' in key:
            all_info_digest = json.loads(data)
            if not client.game_started:
                if (client_id_to_player_number_data := all_info_digest.get('client_id_to_player_number')):
                    _handle_client_id_to_player_number(client_id_to_player_number_data)
                if (client_id_to_team_data := all_info_digest.get('client_id_to_team')):
                    _handle_client_id_to_team(client_id_to_team_data)
            else:
                print('Handling digest!')
                # print(f'Most recent game snapshot: {all_info_digest.get("most_recent_game_state_snapshot")}')
                _handle_most_recent_game_snapshot(all_info_digest.get('most_recent_game_state_snapshot') or '')
                _handle_commands_by_player(all_info_digest.get('commands_by_player') or '{}')
                _handle_commands_by_projectile(all_info_digest.get('commands_by_projectile') or '{}')

        if 'game_started' in key:
            # if data == '1':
            #     start_new_thread(_start_game_on_delay, tuple([]))

            pass

stored_data: list[str] = []


def _start_game_on_delay():
    sleep(3)
    client.set_game_started(True)


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
            print(f'Ignoring {str(packet)[:LOG_CUTOFF]} because this packet has already been handled\n')
    return False


def listen_for_server_updates(socket: Any, client_id_only: bool = False) -> None:
    while True:
        global stored_data
        try:
            # 1048576
            raw_data = receive_compressed_message(socket)
        except Exception as e:
            print(f'Error decompressing data: {e}')
            traceback.print_exc()
            raw_data = ''
            sleep(0.02)
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


def send_all_commands_heartbeats(socket: Any) -> None:
    while True:
        if client.game_started:
            commands_for_player = get_commands_by_player(client_id=client.id)[client.id]

            send_with_retry(socket, f'all_commands_heartbeat|{json.dumps(commands_for_player)}', client_id=client.id)

        sleep(0.25)


def client_main() -> None:
    pygame.init()
    pygame.font.init()

    s: Optional[Any] = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        assert s
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
        assert s
        s.close()

if __name__ == '__main__':
    client_main()