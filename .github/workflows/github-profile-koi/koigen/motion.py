"""Poses: where the koi is, and what its body and fins are doing, per frame.

Every loop closes seamlessly, because each loop holds whole numbers of laps,
tail waves, fin beats and breaths.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .behavior import Behavior

FRAMES_PER_SECOND = 15
BREATHS_PER_LOOP = 5.0
GULPS_PER_LOOP = 3.0


@dataclass
class Pose:
    heading: float  # radians, clockwise on screen from facing right
    center: tuple[float, float]
    depth: float
    wave_phase: float
    wave_strength: float
    tail_spread: float
    pectoral_open: tuple[float, float]
    mouth_open: float
    whisker_sway: float
    bob: float


def _lap_center(size: int) -> tuple[float, float]:
    return (size / 2.0, size / 2.0 + 1.0)


def _lap_radius(size: int, growth: float) -> float:
    return size * (0.20 + 0.05 * growth)


def build_poses(behavior: Behavior, size: int, growth: float) -> list[Pose]:
    frames = behavior.frame_count
    cx, cy = _lap_center(size)
    radius = _lap_radius(size, growth)
    poses: list[Pose] = []

    for index in range(frames):
        t = index / frames
        wave_phase = 2 * math.pi * (2.0 * t)
        breath = math.sin(2 * math.pi * BREATHS_PER_LOOP * t)

        if behavior.laps > 0:
            # a whole number of laps, with a burst at each stroke
            stroke = math.sin(2 * math.pi * (behavior.laps * 2) * t)
            angle = (
                2 * math.pi * behavior.laps * t
                - math.pi / 2
                + 0.22 * behavior.speed * stroke
            )
            px = cx + radius * math.cos(angle)
            py = cy + radius * math.sin(angle)
            heading = angle + math.pi / 2
            poses.append(
                Pose(
                    heading=heading,
                    center=(px, py),
                    depth=behavior.depth,
                    wave_phase=wave_phase + 0.35 * stroke * behavior.speed,
                    wave_strength=0.75 + 0.45 * behavior.speed + 0.25 * stroke,
                    tail_spread=0.05 + 0.07 * abs(stroke),
                    pectoral_open=(
                        0.28 * math.sin(2 * math.pi * 3 * t),
                        0.28 * math.sin(2 * math.pi * 3 * t + math.pi),
                    ),
                    mouth_open=max(0.0, breath) * 0.7,
                    whisker_sway=0.12 * math.sin(2 * math.pi * 2 * t),
                    bob=0.0,
                )
            )
        else:
            drift_x = 2.6 * math.sin(2 * math.pi * t)
            drift_y = 1.6 * math.sin(2 * math.pi * 2 * t + 0.7)
            heading = math.pi * 0.02 * math.sin(2 * math.pi * t)
            if behavior.name == "surface_feeding":
                heading -= 0.10
                drift_y = -size * 0.13 + 1.2 * math.sin(2 * math.pi * 3 * t)
            gulp = max(0.0, math.sin(2 * math.pi * GULPS_PER_LOOP * t))
            poses.append(
                Pose(
                    heading=heading,
                    center=(cx + drift_x, cy + drift_y),
                    depth=behavior.depth,
                    wave_phase=wave_phase * 0.5,
                    wave_strength=0.35 + 0.25 * behavior.speed,
                    tail_spread=0.04,
                    pectoral_open=(
                        0.55 + 0.30 * math.sin(2 * math.pi * 2 * t),
                        0.55 + 0.30 * math.sin(2 * math.pi * 2 * t + math.pi),
                    ),
                    mouth_open=gulp if behavior.gulp else 0.0,
                    whisker_sway=0.18 * math.sin(2 * math.pi * 1.5 * t),
                    bob=0.0,
                )
            )
    return poses


def frame_duration_ms(behavior: Behavior) -> int:
    return round(1000 / FRAMES_PER_SECOND)
