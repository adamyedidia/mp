from enum import Enum
import random


class DeathReason(Enum):
    ARROW = 'arrow'
    DAGGER = 'dagger'


generic_kill_verbs = ['assassinated', 'murdered', 'eliminated', 'killed', 'defeated']
arrow_kill_verbs = ['shot', 'sniped', 'feathered', 'skewered', 'pierced', 'perforated', 'punctured', 'deflated']
dagger_kill_verbs = ['stabbed', 'sliced and diced', 'eviscerated', 'slashed', 'cut', 'backstabbed', 'knifed']


def death_reason_to_verb(death_reason: DeathReason) -> str:
    if death_reason == DeathReason.ARROW:
        return random.choice([*generic_kill_verbs, *arrow_kill_verbs])
    elif death_reason == DeathReason.DAGGER:
        return random.choice([*generic_kill_verbs, *dagger_kill_verbs])
    else:
        return random.choice(generic_kill_verbs)
