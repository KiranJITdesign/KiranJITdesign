"""Body proportions and growth.

Contribution totals set the size. Young koi have a rounder head, larger eyes and
short fins; past the adult total the body keeps lengthening and the fins keep
growing, but the anatomy stops changing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

YOUNG_SHAPE_CONTRIBUTIONS = 1_500
ADULT_CONTRIBUTIONS = 12_750
MAX_GROWTH_CONTRIBUTIONS = 100_000
CONTRIBUTION_SCALE = 50.0

# half-height of the body as a fraction of the maximum, measured from the snout
# (s = 0) to the tail root (s = 1)
_PROFILE = [
    (0.00, 0.30),
    (0.04, 0.52),
    (0.09, 0.72),
    (0.16, 0.89),
    (0.26, 0.98),
    (0.36, 1.00),
    (0.48, 0.96),
    (0.60, 0.86),
    (0.72, 0.71),
    (0.82, 0.54),
    (0.90, 0.40),
    (0.96, 0.31),
    (1.00, 0.26),
]


def growth_fraction(total_contributions: int) -> float:
    """Diminishing returns from zero to one, then flat."""
    bounded = min(max(total_contributions, 0), MAX_GROWTH_CONTRIBUTIONS)
    return math.log2(1.0 + bounded / CONTRIBUTION_SCALE) / math.log2(
        1.0 + MAX_GROWTH_CONTRIBUTIONS / CONTRIBUTION_SCALE
    )


def _profile_at(s: float) -> float:
    s = min(max(s, 0.0), 1.0)
    for index in range(1, len(_PROFILE)):
        s0, h0 = _PROFILE[index - 1]
        s1, h1 = _PROFILE[index]
        if s <= s1:
            t = (s - s0) / (s1 - s0)
            t = t * t * (3 - 2 * t)  # smooth the joins
            return h0 + (h1 - h0) * t
    return _PROFILE[-1][1]


@dataclass
class Anatomy:
    """Everything about the shape that a frame needs, in native pixels."""

    length: float
    half_height: float
    growth: float
    eye_radius: float
    fin_scale: float

    def half_height_at(self, u: float) -> float:
        """u = 0 at the tail root, 1 at the snout."""
        return self.half_height * _profile_at(1.0 - u)

    def wave(self, u: float, phase: float, strength: float) -> float:
        """Vertical offset of the spine, head steady, tail sweeping."""
        reach = (1.0 - u) ** 1.7
        return (
            self.length
            * 0.045
            * reach
            * strength
            * math.sin(2 * math.pi * (0.9 * u) + phase)
        )

    def tail_angle(self, phase: float, strength: float) -> float:
        """Angle of the tail root, which the caudal fin hangs from."""
        return 0.28 * strength * math.sin(phase + 2.1)


def build_anatomy(total_contributions: int) -> Anatomy:
    growth = growth_fraction(total_contributions)
    length = 58.0 + 28.0 * growth
    half_height = length * (0.152 + 0.018 * (1.0 - growth))
    return Anatomy(
        length=length,
        half_height=half_height,
        growth=growth,
        eye_radius=1.9 + 0.5 * (1.0 - growth),
        fin_scale=0.82 + 0.30 * growth,
    )
