from datetime import datetime
import json
from math import sqrt
import random
from socket import socket
from typing import Optional
import pygame
from pygame import Color
from direction import determine_direction_from_keyboard, to_optional_direction
from command import Command, CommandType, get_commands_by_player

from redis_utils import redis_lock, rget, rset

from player import Player
from canvas import Canvas
from client_utils import Client, client
from direction import direction_to_unit_vector

from packet import send_move_command, send_without_retry, send_turn_command
from json.decoder import JSONDecodeError

from utils import MAX_GAME_STATE_SNAPSHOTS

class Game:
    def __init__(self, w: int, h: int, client: Client, socket: socket):
        self.width = w
        self.height = h
        self.client = client
        self.s = socket
        self.player_number = self.client.id if self.client.id is not None else -1
        self.players: dict[int, Player] = {}
        self.player = Player(client.id, 50, 50)
        self.canvas = Canvas(self.width, self.height, "Testing...")

    def run(self):
        print('Running the game!')
        clock = pygame.time.Clock()
        run = True
        if self.player_number < 0:
            print(f'Uh oh, my player number is {self.player_number}, which is messed up')
        while run:
            clock.tick(60)

            if self.player_number < 0:
                self.player_number = self.client.id if self.client.id is not None else -1
                self.players[self.player_number] = self.player
                continue

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    run = False

                if event.type == pygame.MOUSEBUTTONDOWN:
                    assert client.id is not None
                    send_move_command(self.s, x_pos=event.pos[0], y_pos=event.pos[1], client_id=client.id)

                if event.type in [pygame.KEYUP, pygame.KEYDOWN]:
                    if event.key in [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_RIGHT, pygame.K_RIGHT, 
                                     pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN]:
                        direction = determine_direction_from_keyboard()
                        send_turn_command(self.s, direction, client_id=client.id)
                    elif event.key == pygame.K_ESCAPE:
                        run = False

            # for input in [pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN]:
            #     if keys[input]:
            #         self.player.move(input)
            #         self.player.make_valid_position(self.width, self.height)
            #         self.send_data()

            # Update Canvas
            self.canvas.draw_background()
            for player in infer_game_state(client_id=client.id).players:
                player.draw(self.canvas.get_canvas())
            self.canvas.update()

        pygame.quit()

    def send_data(self) -> None:
        data = f'player_state_{self.player_number}|{self.player.to_json()}'
        print(f'Sending: {data}')
        send_without_retry(self.s, data, client_id=client.id)


class GameState:
    def __init__(self, players: list[Player], time: Optional[datetime] = None):
        self.players = players
        self.time = time if time is not None else datetime.now()

    def to_json(self) -> dict:
        return {
            'players': [player.to_json() for player in self.players],
            'time': datetime.timestamp(self.time),
        }

    @classmethod
    def from_json(cls, d: dict) -> 'GameState':
        return GameState(players=[Player.from_json(p) for p in d['players']], 
                         time=datetime.fromtimestamp(d['time']))


game_state_snapshots: list[str] = [json.dumps(GameState([]).to_json())]


def get_game_state_snapshots(*, client_id: Optional[int] = None) -> list[str]:
    if client_id is not None:
        return game_state_snapshots
    else:
        return (json.loads(raw_game_state_snapshots)
                if (raw_game_state_snapshots := rget('game_state_snapshots', client_id=None)) is not None
                else [json.dumps(GameState([]).to_json())])


def _move_player(player: Optional[Player], *, prev_time: datetime, next_time: datetime) -> None:
    if player is None:
        return
    time_elapsed_since_last_command = (next_time - prev_time).total_seconds()
    distance_traveled = player.speed * time_elapsed_since_last_command    
    if player.dest_x is not None and player.dest_y is not None:
        distance_to_dest = sqrt((player.x - player.dest_x)**2 + (player.y - player.dest_y)**2)
        to_dest_unit_vector_x = (player.dest_x - player.x) / distance_to_dest if distance_to_dest > 0 else 0
        to_dest_unit_vector_y = (player.dest_y - player.y) / distance_to_dest if distance_to_dest > 0 else 0
        if distance_to_dest < distance_traveled or distance_to_dest <= 0:
            player.x = player.dest_x
            player.y = player.dest_y
        else:
            player.x += int(to_dest_unit_vector_x * distance_traveled)
            player.y += int(to_dest_unit_vector_y * distance_traveled)
    elif player.direction is not None:
        unit_vector_x, unit_vector_y = direction_to_unit_vector(player.direction)
        player.x += int(unit_vector_x * distance_traveled)
        player.y += int(unit_vector_y * distance_traveled)


def _run_commands_for_player(starting_time: datetime, player: Optional[Player], 
                             commands_for_player: list[Command], 
                             player_client_id: int,
                             end_time: Optional[datetime] = None) -> Optional[Player]:
    if end_time is None:
        end_time = datetime.now()
    current_time = starting_time
    for command in commands_for_player:
        if player is None and command.type != CommandType.SPAWN:
            continue
        if command.time < starting_time:
            continue
        _move_player(player, prev_time=current_time, next_time=command.time)
        if command.type == CommandType.MOVE:
            assert player is not None
            assert command.data is not None
            player.dest_x = command.data['x']
            player.dest_y = command.data['y']
        elif command.type == CommandType.SPAWN:
            assert command.data is not None
            player = Player(client_id=player_client_id, startx=command.data['x'], starty=command.data['y'])      
        elif command.type == CommandType.TURN:
            assert player is not None
            assert command.data is not None
            player.direction = to_optional_direction(command.data['dir'])
            player.dest_x = None
            player.dest_y = None
        current_time = command.time
    _move_player(player, prev_time=current_time, next_time=end_time)

    return player


def lists_are_equal(l1: list[str], l2: list[str]) -> bool:
    if len(l1) != len(l2):
        return False
    for i in range(len(l1)):
        if l1[i] != l2[i]:
            return False
    return True


def infer_game_state(*, client_id: Optional[int] = None) -> GameState:
    raw_snaps = get_game_state_snapshots(client_id=client_id)
    assert len(raw_snaps) > 0
    raw_snap_to_run_forward_from = raw_snaps[0] if len(raw_snaps) < 3 else raw_snaps[-2]
    snap_to_run_forward_from = GameState.from_json(json.loads(raw_snap_to_run_forward_from))
    raw_commands_by_player = get_commands_by_player(client_id=client_id)
    player_ids_commands_have_been_run_for: set[int] = set()
    final_players: list[Player] = []
    player: Optional[Player] = None
    player_client_id = None
    for player in snap_to_run_forward_from.players:
        assert player is not None
        player_client_id = player.client_id
        player_ids_commands_have_been_run_for.add(player_client_id)
        raw_commands_for_player = raw_commands_by_player.get(player_client_id) or []
        commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands_for_player], 
                                     key=lambda c: c.time)
        player = _run_commands_for_player(snap_to_run_forward_from.time, player.copy(), commands_for_player, player_client_id)
        if player:
            final_players.append(player)

    for player_client_id, raw_commands_for_player in raw_commands_by_player.items():
        if player_client_id in player_ids_commands_have_been_run_for:
            continue
        player_ids_commands_have_been_run_for.add(player_client_id)
        commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands_for_player], 
                                     key=lambda c: c.time)        
        player = _run_commands_for_player(snap_to_run_forward_from.time, None, commands_for_player, player_client_id)
        if player:
            final_players.append(player)

    return GameState(players=final_players, time=datetime.now())

        
def infer_and_store_game_state_snap() -> None:
    game_state_snapshots = get_game_state_snapshots()
    new_snapshot = infer_game_state(client_id=None)
    game_state_snapshots.append(json.dumps(new_snapshot.to_json()))
    if len(game_state_snapshots) > MAX_GAME_STATE_SNAPSHOTS:
        del game_state_snapshots[0]
    rset('game_state_snapshots', json.dumps(game_state_snapshots), client_id=None)
    rset('most_recent_game_state_snapshot', json.dumps(new_snapshot.to_json()), client_id=None)
