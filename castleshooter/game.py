from datetime import datetime, timedelta
import json
from math import sqrt
import math
import random
from socket import socket
from typing import Any, Optional
import pygame
from pygame import Color
from announcement import Announcement, get_announcement_idempotency_key_for_command
from weapon import Weapon, weapon_to_pygame_image, DAGGER_RANGE
from death_reason import DeathReason, death_reason_to_verb
from command import get_commands_by_projectile
from packet import send_eat_arrow_command, send_remove_projectile_command, send_die_command, send_spawn_command
from projectile import projectile_intersects_player, draw_arrow, ARROW_COLOR
from projectile import generate_projectile_id, Projectile, ProjectileType
from direction import determine_direction_from_keyboard, to_optional_direction
from command import Command, CommandType, get_commands_by_player

from redis_utils import redis_lock, rget, rset

from player import Player, BASE_MAX_HP
from canvas import Canvas
from client_utils import Client, client
from direction import direction_to_unit_vector

from packet import (
    send_move_command, send_without_retry, send_turn_command, send_spawn_projectile_command, send_teleport_command,
    send_lose_hp_command,
)
from json.decoder import JSONDecodeError

from utils import MAX_GAME_STATE_SNAPSHOTS, LOG_CUTOFF, draw_text_centered_on_rectangle


SHIFT_KEYS = [pygame.K_RSHIFT, pygame.K_LSHIFT]
NUMBER_KEYS = {1: pygame.K_1, 
               2: pygame.K_2, 
               3: pygame.K_3, 
               4: pygame.K_4, 
               5: pygame.K_5, 
               6: pygame.K_6, 
               7: pygame.K_7, 
               8: pygame.K_8}

class Game:
    def __init__(self, w: int, h: int, client: Client, socket: socket):
        self.width = w
        self.height = h
        self.client = client
        self.s = socket
        self.player_number = self.client.id if self.client.id is not None else -1
        self.players: dict[int, Player] = {}
        self.player: Optional[Player] = Player(client.id, 300, 300)
        self.canvas = Canvas(self.width, self.height, "Testing...")
        self.announcements: list[Announcement] = []
        self.commands_handled: list[Command] = []
        self.target: Optional[Player] = None
        self.mouse_target: Optional[Player] = None

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

            game_state = infer_game_state(client_id=client.id)
            for player in game_state.players:
                if player.client_id == client.id:
                    if self.player is not None:
                        self.player.update_info_from_inferred_game_state(player)
                    else:
                        self.player = player

            client_player = self.player
            target = self.target

            if client_player is not None:
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
                        elif event.key == pygame.K_SPACE:
                            pressed = pygame.key.get_pressed()
                            if pressed[pygame.K_SPACE]:
                                if client_player.weapon == Weapon.BOW and client_player.ammo > 0:
                                    mouse_x, mouse_y = pygame.mouse.get_pos()
                                    arrow_distance = 400
                                    vector_from_player_to_mouse = (mouse_x - client_player.x, mouse_y - client_player.y)
                                    vector_from_player_to_mouse_mag = math.sqrt(vector_from_player_to_mouse[0]**2 + vector_from_player_to_mouse[1]**2)
                                    unit_vector_from_player_to_mouse = (vector_from_player_to_mouse[0] / vector_from_player_to_mouse_mag,
                                                                        vector_from_player_to_mouse[1] / vector_from_player_to_mouse_mag)
                                    arrow_dest_x = client_player.x + unit_vector_from_player_to_mouse[0] * arrow_distance
                                    arrow_dest_y = client_player.y + unit_vector_from_player_to_mouse[1] * arrow_distance
                                    send_spawn_projectile_command(self.s, generate_projectile_id(), client_player.x, client_player.y, arrow_dest_x, arrow_dest_y, [client.id],
                                                                type=ProjectileType.ARROW, client_id=client.id)
                                    # send_shoot_command(self.s, generate_projectile_id(), client_player.x, client_player.y, arrow_dest_x, arrow_dest_y, type=ProjectileType.ARROW)
                                    client_player.ammo -= 1
                                elif client_player.weapon == Weapon.DAGGER and target is not None:
                                    send_lose_hp_command(self.s, client_player.client_id, target.client_id, death_reason_to_verb(DeathReason.DAGGER), 2, client_id=client.id)
                                    send_teleport_command(self.s, target.x, target.y, client_id=client.id)

                        elif event.key in [*SHIFT_KEYS, *NUMBER_KEYS.values()]:
                            pressed = pygame.key.get_pressed()
                            shift_pressed = False
                            number_pressed: Optional[int] = None
                            for key in SHIFT_KEYS:
                                if pressed[key]:
                                    shift_pressed = True
                            for number, key in NUMBER_KEYS.items():
                                if pressed[key]:
                                    number_pressed = number
                            if shift_pressed and number_pressed is not None and client_player.weapon == Weapon.DAGGER:
                                pressed_target_id = number_pressed
                                for pressed_target in target.players:
                                    if pressed_target.id == pressed_target_id and sqrt((player.x - client_player.x)**2 + (player.y - client_player.y)**2) < DAGGER_RANGE:
                                        send_lose_hp_command(self.s, client_player.client_id, pressed_target_id, death_reason_to_verb(DeathReason.DAGGER), 2, client_id=client.id)
                                        send_teleport_command(self.s, pressed_target.x, pressed_target.y, client_id=client.id)

                        elif event.key == pygame.K_ESCAPE:
                            run = False

                for projectile in game_state.projectiles:
                    if projectile_intersects_player(projectile, client_player) and not client.id in projectile.friends:
                        if projectile.type == ProjectileType.ARROW:
                            start_of_arrow_x, start_of_arrow_y = projectile.get_start_of_arrow()
                            send_eat_arrow_command(self.s,
                                                start_of_arrow_x - client_player.x,
                                                start_of_arrow_y - client_player.y,
                                                projectile.x - client_player.x,
                                                projectile.y - client_player.y,
                                                client_id=client.id)
                            send_remove_projectile_command(self.s, projectile.id, client_id=client.id)
                            client_player.hp -= 1
                            self.maybe_die(client_player, DeathReason.ARROW, projectile.player_id)

                            if client_player.hp == 0:
                                death_reason = DeathReason.ARROW
                                verb = death_reason_to_verb(death_reason)
                                command = send_die_command(self.s, projectile.player_id, verb, client_id=client.id)                                
                                killer_id = projectile.player_id
                                message = f'Player {killer_id} {verb} you!'
                                self.add_announcement(Announcement(get_announcement_idempotency_key_for_command(command), 
                                                                   datetime.now(), message))
                                self.player = None

            else:
                for event in pygame.event.get():
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                        send_spawn_command(self.s, 300, 300, client_id=client.id)

            self.target = None
            min_distance = DAGGER_RANGE
            if client_player.weapon == Weapon.DAGGER:
                for possible_target in game_state.players:
                    if possible_target.client_id != client_player.client_id:
                        distance = sqrt((possible_target.x - client_player.x)**2 + (possible_target.y - client_player.y)**2)
                        if distance < min_distance:
                            self.target = possible_target
                            min_distance = distance                 

            # for input in [pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP, pygame.K_DOWN]:
            #     if keys[input]:
            #         self.player.move(input)
            #         self.player.make_valid_position(self.width, self.height)
            #         self.send_data()

            # Update Canvas
            self.canvas.draw_background()
            canvas = self.canvas.get_canvas()
            for player in game_state.players:
                player.draw(canvas)
                if target is not None and player.client_id != client_player.client_id and player.client_id == target.client_id:
                    pygame.draw.circle(canvas, (0,0,0), (player.x, player.y), 40, width=2)
            for projectile in game_state.projectiles:
                projectile.draw(canvas)
            self.draw_health_state(canvas)
            self.draw_announcements(canvas)
            self.draw_big_text(canvas)
            self.draw_weapon_and_ammo(canvas)
            self.canvas.update()

        pygame.quit()

    def draw_health_state(self, canvas: Any) -> None:
        if self.player is None:
            return
        current_x = 25
        current_y = 25
        for i in range(max(BASE_MAX_HP, self.player.hp)):
            if i >= self.player.hp:
                image_surface = pygame.image.load('assets/empty_heart.png').convert_alpha()
            elif i >= BASE_MAX_HP:
                image_surface = pygame.image.load('assets/blue_heart.png').convert_alpha()
            else:
                image_surface = pygame.image.load('assets/heart.png').convert_alpha()
            canvas.blit(image_surface, (current_x, current_y))
            current_x += 75

    def maybe_die(self, client_player: Player, verb: str, killer_id: int) -> None:
        if client_player.hp <= 0:
            command = send_die_command(self.s, killer_id, verb, client_id=client.id)                                
            message = f'Player {killer_id} {verb} you!'
            self.add_announcement(Announcement(get_announcement_idempotency_key_for_command(command), 
                                                datetime.now(), message))
            self.player = None        

    def add_announcement(self, annoucement: Announcement) -> None:
        self.announcements = [a for a in self.announcements if a.time > datetime.now() - timedelta(seconds=15)]
        self.announcements.append(annoucement)
        self.announcements = self.announcements[-5:]        

    def draw_announcements(self, canvas: Any) -> None:
        current_x = 25
        current_y = self.height - 150
        font = pygame.font.SysFont("comicsans", 25)
        self.announcements = [a for a in self.announcements if a.time > datetime.now() - timedelta(seconds=15)]
        self.announcements = self.announcements[-5:]

        # print([a.message for a in self.announcements])

        for announcement in self.announcements:
            if announcement.time > datetime.now() - timedelta(seconds=10):
                opacity = 1.0
            elif announcement.time < datetime.now() - timedelta(seconds=15):
                opacity = 0.0
            else:
                opacity = 1 - (datetime.now() - announcement.time - timedelta(seconds=10)).total_seconds()/5.0
            text = font.render(announcement.message, True, (0, 0, 0))
            text.set_alpha(int(255 * opacity))
            canvas.blit(text, (current_x, current_y))
            current_y += 25

    def draw_big_text(self, canvas: Any) -> None:
        if self.player is None:
            draw_text_centered_on_rectangle(canvas, 'You died. Press enter to respawn.', 0, 0, self.width, self.height, 35)
            # font = pygame.font.SysFont("comicsans", 35)
            # text = font.render('You died. Press enter to respawn.', True, (0, 0, 0))
            # canvas.blit(text, (120, 350))

    def draw_weapon_and_ammo(self, canvas: Any) -> None:
        if self.player and self.player.weapon:
            current_x = self.width - 110
            current_y = self.height - 110
            image_surface = pygame.transform.scale(weapon_to_pygame_image(self.player.weapon), (100, 100)).convert_alpha()
            canvas.blit(image_surface, (current_x, current_y))

            arrow_bottom = self.height - 55
            arrow_top = self.height - 85

            if self.player.weapon == Weapon.BOW:
                for _ in range(self.player.ammo):
                    current_x -= 30
                    draw_arrow(canvas, ARROW_COLOR, (current_x, arrow_bottom), (current_x, arrow_top))


class GameState:
    def __init__(self, players: list[Player], projectiles: list[Projectile], time: Optional[datetime] = None):
        self.players = players
        self.projectiles = projectiles
        self.time = time if time is not None else datetime.now()

    def to_json(self) -> dict:
        return {
            'players': [player.to_json() for player in self.players],
            'projectiles': [projectile.to_json() for projectile in self.projectiles],
            'time': datetime.timestamp(self.time),
        }

    @classmethod
    def from_json(cls, d: dict) -> 'GameState':
        return GameState(players=[Player.from_json(p) for p in d['players']], 
                         projectiles=[Projectile.from_json(p) for p in d['projectiles']],
                         time=datetime.fromtimestamp(d['time']))


game_state_snapshots: list[str] = [json.dumps(GameState([], []).to_json())]


def get_game_state_snapshots(*, client_id: Optional[int] = None) -> list[str]:
    if client_id is not None:
        return game_state_snapshots
    else:
        return (json.loads(raw_game_state_snapshots)
                if (raw_game_state_snapshots := rget('game_state_snapshots', client_id=None)) is not None
                else [json.dumps(GameState([], []).to_json())])


def _move_projectile(projectile: Optional[Projectile], *, prev_time: datetime, next_time: datetime) -> Optional[Projectile]:
    if projectile is None:
        return None
    time_elapsed_since_last_command = (next_time - prev_time).total_seconds()
    distance_traveled = projectile.speed * time_elapsed_since_last_command    
    if projectile.dest_x is not None and projectile.dest_y is not None:
        distance_to_dest = sqrt((projectile.x - projectile.dest_x)**2 + (projectile.y - projectile.dest_y)**2)
        to_dest_unit_vector_x = (projectile.dest_x - projectile.x) / distance_to_dest if distance_to_dest > 0 else 0
        to_dest_unit_vector_y = (projectile.dest_y - projectile.y) / distance_to_dest if distance_to_dest > 0 else 0
        if distance_to_dest < distance_traveled or distance_to_dest <= 0:
            return None
        else:
            projectile.x += int(to_dest_unit_vector_x * distance_traveled)
            projectile.y += int(to_dest_unit_vector_y * distance_traveled)
        return projectile
    return None


def _run_commands_for_projectile(starting_time: datetime, projectile: Optional[Projectile],
                               commands_for_projectile: list, projectile_id: int, 
                               end_time: Optional[datetime] = None) -> Optional[Projectile]:
    if end_time is None:
        end_time = datetime.now()
    current_time = starting_time    
    for command in commands_for_projectile:
        if projectile is None and command.type != CommandType.SPAWN_PROJECTILE:
            continue
        if command.time < starting_time:
            continue
        if command.time > end_time:
            break
        projectile = _move_projectile(projectile, prev_time=current_time, next_time=command.time)
        if command.type == CommandType.SPAWN_PROJECTILE:
            assert command.data is not None
            projectile = Projectile.from_json(command.data)
        elif command.type == CommandType.REMOVE_PROJECTILE:
            return None
    projectile = _move_projectile(projectile, prev_time=current_time, next_time=end_time)

    return projectile


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
                             all_projectiles: list[Projectile],
                             end_time: Optional[datetime] = None) -> Optional[Player]:
    if end_time is None:
        end_time = datetime.now()
    current_time = starting_time
    raw_commands_by_projectile = get_commands_by_projectile(client_id=client.id)    
    for command in commands_for_player:
        if player is None and command.type != CommandType.SPAWN:
            continue
        if command.time < starting_time:
            continue
        if command.time > end_time:
            break
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
        elif command.type == CommandType.SPAWN_PROJECTILE:
            assert command.data is not None
            projectile: Optional[Projectile] = Projectile.from_json(command.data)
            assert projectile
            projectile_id = projectile.id            
            raw_commands_for_projectile = raw_commands_by_projectile.get(projectile_id) or []
            commands_for_projectile = sorted([Command.from_json(json.loads(c)) for c in raw_commands_for_projectile], 
                                        key=lambda c: c.time)            
            projectile = _run_commands_for_projectile(command.time, projectile, commands_for_projectile, projectile.id, end_time)
            if projectile and projectile.id not in [p.id for p in all_projectiles]:
                all_projectiles.append(projectile)
        elif command.type == CommandType.EAT_ARROW:
            assert command.data is not None
            assert player is not None
            player.arrows_puncturing.append([[command.data['arrow_start_x'], command.data['arrow_start_y']],
                                             [command.data['arrow_end_x'], command.data['arrow_end_y']]])
        elif command.type == CommandType.DIE:
            player = None
        elif command.type == CommandType.TELEPORT:
            assert command.data is not None
            assert player is not None
            player.x = command.data['x']
            player.y = command.data['y']
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


def infer_game_state(*, end_time: Optional[datetime] = None, client_id: Optional[int] = None) -> GameState:
    if end_time is None:
        end_time = datetime.now()
    raw_snaps = get_game_state_snapshots(client_id=client_id)
    assert len(raw_snaps) > 0
    if client_id is not None:
        raw_snap_to_run_forward_from = raw_snaps[-1]
    else:
        raw_snap_to_run_forward_from = raw_snaps[0]
    snap_to_run_forward_from = GameState.from_json(json.loads(raw_snap_to_run_forward_from))
    raw_commands_by_player = get_commands_by_player(client_id=client_id)
    raw_commands_by_projectile = get_commands_by_projectile(client_id=client_id)
    player_ids_commands_have_been_run_for: set[int] = set()
    final_players: list[Player] = []
    player: Optional[Player] = None
    player_client_id = None
    all_projectiles: list[Projectile] = []
    for projectile in snap_to_run_forward_from.projectiles:
        assert projectile is not None
        projectile_id = projectile.id
        raw_commands_for_projectile = raw_commands_by_projectile.get(projectile_id) or []
        commands_for_projectile = sorted([Command.from_json(json.loads(c)) for c in raw_commands_for_projectile], 
                                     key=lambda c: c.time)
        new_projectile = _run_commands_for_projectile(snap_to_run_forward_from.time, projectile.copy(), commands_for_projectile, 
                                                  projectile_id, end_time=end_time)
        if new_projectile and new_projectile.id not in [p.id for p in all_projectiles]:
            all_projectiles.append(new_projectile)                                                  

    for player in snap_to_run_forward_from.players:
        assert player is not None
        player_client_id = player.client_id
        player_ids_commands_have_been_run_for.add(player_client_id)
        raw_commands_for_player = raw_commands_by_player.get(player_client_id) or []
        commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands_for_player], 
                                     key=lambda c: c.time)
        player = _run_commands_for_player(snap_to_run_forward_from.time, player.copy(), commands_for_player, player_client_id,
                                          all_projectiles, end_time=end_time)
        if player:
            final_players.append(player)

    for player_client_id, raw_commands_for_player in raw_commands_by_player.items():
        if player_client_id in player_ids_commands_have_been_run_for:
            continue
        player_ids_commands_have_been_run_for.add(player_client_id)
        commands_for_player = sorted([Command.from_json(json.loads(c)) for c in raw_commands_for_player], 
                                     key=lambda c: c.time)        
        player = _run_commands_for_player(snap_to_run_forward_from.time, None, commands_for_player, player_client_id,
                                          all_projectiles, end_time=end_time)
        if player:
            final_players.append(player)

    return GameState(players=final_players, projectiles=all_projectiles, time=end_time)


num_snaps_inferred = 0

        
def infer_and_store_game_state_snap() -> None:
    global num_snaps_inferred
    num_snaps_inferred += 1
    game_state_snapshots: list[str] = get_game_state_snapshots()
    new_snapshot = infer_game_state(client_id=None, end_time=datetime.now() - timedelta(seconds=3))
    game_state_snapshots.append(json.dumps(new_snapshot.to_json()))
    if num_snaps_inferred % 8 == 0:
        print(f'Culling snapshots: {len(game_state_snapshots)}')
        game_state_snapshots = [s for s in game_state_snapshots if datetime.now() - datetime.fromtimestamp(json.loads(s)['time']) < timedelta(seconds=7)]
        print(f'Culling snapshots: {len(game_state_snapshots)}')        
    rset('game_state_snapshots', json.dumps(game_state_snapshots), client_id=None)
    rset('most_recent_game_state_snapshot', json.dumps(new_snapshot.to_json()), client_id=None)
