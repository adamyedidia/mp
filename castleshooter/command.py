from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
import json

from typing import Optional
from redis_utils import redis_lock, rget, rset

from utils import MAX_GAME_STATE_SNAPSHOTS, SNAPSHOTS_CREATED_EVERY, to_optional_int, remove_nones


commands_by_player: dict[int, list[str]] = defaultdict(list)
commands_by_projectile: dict[int, list[str]] = defaultdict(list)


class CommandType(Enum):
    MOVE = 'move'
    SPAWN = 'spawn'
    SPAWN_PROJECTILE = 'spawn_projectile'
    TURN = 'turn'
    SHOOT = 'shoot'
    EAT_ARROW = 'eat_arrow'
    REMOVE_PROJECTILE = 'remove_projectile'
    DIE = 'die'
    LOSE_HP = 'lose_hp'
    TELEPORT = 'teleport'


PROJECTILE_COMMAND_TYPES = [CommandType.REMOVE_PROJECTILE]


class Command():
    def __init__(self, id: int, type: CommandType, time: Optional[datetime] = None, 
                 client_id: Optional[int] = None,
                 data: Optional[dict] = None):
        self.id = id
        self.type = type
        self.time = time if time is not None else datetime.now()
        self.client_id = client_id
        self.data = data

    def to_json(self) -> dict:
        return {
            'id': self.id,
            'type': self.type.value,
            'time': datetime.timestamp(self.time),
            **remove_nones({'client_id': self.client_id,
                            'data': self.data}),
        }

    @classmethod
    def from_json(cls, d: dict) -> 'Command':
        return Command(id=d['id'], type=CommandType(d['type']), time=datetime.fromtimestamp(d['time']), 
                       **remove_nones({'data': d.get('data'),
                                       'client_id': d.get('client_id')}))


def get_commands_by_player(*, client_id: Optional[int] = None) -> dict[int, list[str]]:
    if client_id is not None:
        return commands_by_player
    else:
        return {int(key): val for key, val in json.loads(rget('commands_by_player', client_id=None) or '{}').items()}


def get_commands_by_projectile(*, client_id: Optional[int] = None) -> dict[int, list[str]]:
    if client_id is not None:
        return commands_by_projectile
    else:
        return {int(key): val for key, val in json.loads(rget('commands_by_projectile', client_id=None) or '{}').items()}    


def store_command(command: Command, *, for_client: int, 
                  client_id: Optional[int] = None) -> None:
    command_str = json.dumps(command.to_json())
    is_projectile_command = (command.type in PROJECTILE_COMMAND_TYPES)
    global commands_by_player
    if client_id is not None:
        if is_projectile_command:
            assert command.data
            commands_by_projectile[command.data['projectile_id']].append(command_str)
        else:
            commands_by_player[for_client].append(command_str)
    else:
        if command.time < datetime.now() - timedelta(seconds=2):
            return
        commands = get_commands_by_projectile(client_id=None) if is_projectile_command else get_commands_by_player(client_id=None)
        command_id = command.data['projectile_id'] if is_projectile_command else command.client_id  # type: ignore
        with redis_lock(f'add_command_for_player_redis_key_{client_id}', client_id=None):
            assert command_id is not None
            if command_id in commands:
                l = commands[command_id]
                commands[command_id] = [c for c in l if datetime.fromtimestamp(json.loads(c)['time']) > datetime.now() - timedelta(seconds=20)]
                commands[command_id].append(command_str)
            else:
                commands[command_id] = [command_str]
            rset('commands_by_projectile' if is_projectile_command else 'commands_by_player', json.dumps(commands), client_id=None)
