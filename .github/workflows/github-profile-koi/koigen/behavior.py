"""The day's movement, chosen from recent activity.

The first matching rule wins:

| Behavior        | When the observed day ...                                  |
| --------------- | ---------------------------------------------------------- |
| Deep rest       | ends 60 or more quiet days                                  |
| Rest            | ends 14 or more quiet days                                  |
| Surface feeding | is the first day with contributions in its Monday-Sunday week |
| Dart            | falls within a week of the total crossing a milestone, or a Sunday finishes a busy week |
| Cruise          | is anything else                                            |
"""

from __future__ import annotations

from dataclasses import dataclass

DEEP_REST_QUIET_DAYS = 60
REST_QUIET_DAYS = 14
DART_MILESTONES = (1_000, 5_000, 10_000, 25_000, 50_000, 100_000)
DART_COMPARED_WEEKS = 52
DART_MIN_COMPLETE_WEEKS = 10
DART_WEEK_SHARE_DENOMINATOR = 10


@dataclass
class Behavior:
    name: str
    frame_count: int
    depth: float
    speed: float
    laps: float
    gulp: bool

    @property
    def label(self) -> str:
        return self.name.replace("_", " ")


CRUISE = Behavior("cruise", 120, 0.0, 1.0, 1.0, False)
DART = Behavior("dart", 120, 0.0, 2.1, 2.0, False)
REST = Behavior("rest", 90, 0.22, 0.35, 0.0, True)
DEEP_REST = Behavior("deep_rest", 120, 0.5, 0.18, 0.0, True)
SURFACE_FEEDING = Behavior("surface_feeding", 90, -0.05, 0.3, 0.0, True)


def _quiet_days(day_counts: list[int]) -> int:
    """How many days back from the observation date were empty."""
    count = 0
    for value in reversed(day_counts):
        if value > 0:
            break
        count += 1
    return count


def _week_of(days: list[dict]) -> list[int]:
    """The Monday-Sunday week that contains the observation date."""
    if not days:
        return []
    week = []
    for day in reversed(days):
        week.append(int(day.get("count", 0)))
        if len(week) == 7:
            break
    return list(reversed(week))


def select_behavior(snapshot: dict) -> Behavior:
    days = snapshot.get("days") or []
    counts = [int(day.get("count", 0)) for day in days]
    quiet = _quiet_days(counts)
    if quiet >= DEEP_REST_QUIET_DAYS:
        return DEEP_REST
    if quiet >= REST_QUIET_DAYS:
        return REST

    week = _week_of(days)
    if week and week[-1] > 0 and all(day == 0 for day in week[:-1]):
        return SURFACE_FEEDING

    total = int(snapshot.get("total_contributions", 0))
    recent = sum(counts[-7:])
    earlier = max(total - recent, 0)
    if any(earlier < milestone <= total for milestone in DART_MILESTONES):
        return DART

    if snapshot.get("busy_week"):
        return DART
    return CRUISE
