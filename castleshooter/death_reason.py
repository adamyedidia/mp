from enum import Enum
import random


class DeathReason(Enum):
    ARROW = 'arrow'


generic_kill_verbs = ['assassinated', 'murdered', 'eliminated', 'killed']
arrow_kill_verbs = ['shot', 'sniped', 'feathered', 'skewered', 'pierced', 'perforated', 'punctured', 'deflated']


def death_reason_to_verb(death_reason: DeathReason) -> str:
    if death_reason == DeathReason.ARROW:
        return random.choice([*generic_kill_verbs, *arrow_kill_verbs])
    else:
        return random.choice(generic_kill_verbs)
