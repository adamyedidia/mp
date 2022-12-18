from collections import defaultdict
from typing import Optional

from team import Team
import time
import random


class Score:
    def __init__(self):
        self.scored_points: list[tuple[Team, float]] = []
    
    def increment(self, team: Team, max_delay_seconds: Optional[int] = None) -> None:
        if max_delay_seconds is None:
            self.scored_points.append((team, time.time()))
        else:
            self.scored_points.append((team, time.time() + max_delay_seconds * random.random()))

    def get(self, actual: bool = False) -> tuple[int, int]:
        red_score = 0
        blue_score = 0
        for scored_point in self.scored_points:
            if scored_point[1] < time.time() or actual:
                if scored_point[0] == Team.RED:
                    red_score += 1
                else:
                    blue_score += 1

        return (red_score, blue_score)        


score = Score()
