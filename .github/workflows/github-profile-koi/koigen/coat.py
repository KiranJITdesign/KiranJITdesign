"""Bodies, pigments and the coat that a koi wears.

The body is a four-step ramp (light on the back, dark on the belly). Each of the
account's counted languages becomes a pigment, and each pigment owns a few
organic blobs painted onto the body. The blobs are placed from a seed derived
from the account id, so the same account always draws the same fish.
"""

from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass, field

# --- palettes ---------------------------------------------------------------

# light -> dark, four steps, sampled down the flank
BODY_RAMPS: dict[str, list[tuple[int, int, int]]] = {
    "white": [(255, 255, 255), (246, 248, 253), (219, 226, 240), (176, 186, 208)],
    "black": [(62, 72, 108), (40, 46, 74), (25, 22, 40), (16, 14, 27)],
    "asagi": [(206, 222, 238), (158, 186, 214), (116, 148, 188), (84, 112, 152)],
    "tea": [(219, 186, 138), (190, 150, 102), (154, 116, 76), (116, 86, 58)],
    "gold": [(255, 231, 152), (252, 200, 92), (228, 162, 56), (186, 122, 40)],
    "platinum": [(248, 251, 255), (218, 226, 242), (182, 192, 216), (144, 154, 182)],
}

BODY_NAMES = tuple(BODY_RAMPS)

# pigment ramps are three steps, applied with the same light direction
PIGMENT_RAMPS: dict[str, list[tuple[int, int, int]]] = {
    "red": [(255, 150, 112), (231, 84, 60), (176, 48, 42)],
    "orange": [(254, 192, 84), (247, 132, 42), (194, 82, 34)],
    "yellow": [(255, 240, 156), (250, 208, 88), (200, 152, 46)],
    "blue": [(122, 212, 246), (32, 142, 206), (24, 78, 140)],
    "green": [(152, 222, 152), (60, 172, 112), (30, 110, 80)],
    "purple": [(202, 162, 242), (142, 102, 202), (90, 60, 142)],
    "black": [(72, 82, 118), (46, 52, 80), (26, 22, 40)],
    "white": [(255, 255, 255), (240, 243, 250), (208, 214, 228)],
}

FIN_RAMPS: dict[str, list[tuple[int, int, int]]] = {
    "pale": [(255, 255, 255), (230, 238, 250), (198, 210, 232)],
    "gold": [(255, 242, 196), (250, 208, 124), (212, 158, 72)],
    "silver": [(248, 250, 255), (214, 224, 240), (170, 182, 206)],
    "smoke": [(96, 106, 140), (64, 72, 104), (40, 44, 68)],
}

OUTLINE = (26, 22, 40)

# how far a pigment drifts from the plain body when the account is vivid
DULL_SATURATION = 0.3
VIVID_SATURATION_GAIN = 0.35
DULL_DARKENING = 0.16
VIVID_BRIGHTENING = 0.10


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return low if value < low else high if value > high else value


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = clamp(t)
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def adjust(
    color: tuple[int, int, int], saturation: float, brightness: float
) -> tuple[int, int, int]:
    r, g, b = (channel / 255 for channel in color)
    h, light, s = colorsys.rgb_to_hls(r, g, b)
    s = clamp(s * saturation)
    light = clamp(light * brightness)
    r, g, b = colorsys.hls_to_rgb(h, light, s)
    return (round(r * 255), round(g * 255), round(b * 255))


# --- deterministic noise ----------------------------------------------------


def _hash2(seed: int, ix: int, iy: int) -> float:
    n = (ix * 374761393 + iy * 668265263 + seed * 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFFFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def _smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def value_noise(seed: int, x: float, y: float) -> float:
    """Bilinear value noise in [0, 1], smooth enough to read as a soft edge."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = _smoothstep(x - ix), _smoothstep(y - iy)
    a = _hash2(seed, ix, iy)
    b = _hash2(seed, ix + 1, iy)
    c = _hash2(seed, ix, iy + 1)
    d = _hash2(seed, ix + 1, iy + 1)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def fractal_noise(seed: int, x: float, y: float, octaves: int = 3) -> float:
    total, amplitude, norm = 0.0, 1.0, 0.0
    for octave in range(octaves):
        total += amplitude * value_noise(seed + octave * 7919, x * (2**octave), y * (2**octave))
        norm += amplitude
        amplitude *= 0.5
    return total / norm


# --- pigments ---------------------------------------------------------------


def pigment_for_language(name: str | None, color_hex: str | None) -> str:
    """Bucket a language colour into one of the eight koi pigments."""
    rgb = None
    if color_hex and color_hex.startswith("#") and len(color_hex) == 7:
        try:
            rgb = tuple(int(color_hex[i : i + 2], 16) for i in (1, 3, 5))
        except ValueError:
            rgb = None
    if rgb is None:
        return "black"

    r, g, b = (channel / 255 for channel in rgb)
    hue, light, saturation = colorsys.rgb_to_hls(r, g, b)
    if saturation < 0.18 or light < 0.16:
        return "black"
    degrees = hue * 360
    if degrees < 12 or degrees >= 345:
        return "red"
    if degrees < 40:
        return "orange"
    if degrees < 70:
        return "yellow"
    if degrees < 165:
        return "green"
    if degrees < 260:
        return "blue"
    if degrees < 320:
        return "purple"
    return "red"


@dataclass
class Blob:
    """One patch of pigment, in body coordinates (u along, v across)."""

    u: float
    v: float
    ru: float
    rv: float
    seed: int
    wobble: float

    def contains(self, u: float, v: float) -> bool:
        if abs(u - self.u) > self.ru * 1.6 or abs(v - self.v) > self.rv * 1.6:
            return False
        du = (u - self.u) / self.ru
        dv = (v - self.v) / self.rv
        edge = 1.0 + (fractal_noise(self.seed, u * 14, v * 7) - 0.5) * self.wobble
        return du * du + dv * dv <= edge


@dataclass
class Coat:
    body: str
    ramp: list[tuple[int, int, int]]
    fin_ramp: list[tuple[int, int, int]]
    patterns: list[tuple[str, list[Blob]]] = field(default_factory=list)
    net: bool = False
    net_color: tuple[int, int, int] = (58, 68, 102)
    seed: int = 0

    def pigment_at(self, u: float, v: float) -> str | None:
        for pigment, blobs in self.patterns:
            for blob in blobs:
                if blob.contains(u, v):
                    return pigment
        return None


def _pattern_blobs(
    rng: random.Random, pigment: str, share: float, seed: int
) -> list[Blob]:
    """Place the blobs for one pigment so that their area follows its share."""
    if pigment == "black":
        count = max(1, min(4, round(1 + share * 6)))
        blobs = []
        for _ in range(count):
            blobs.append(
                Blob(
                    u=rng.uniform(0.18, 0.92),
                    v=rng.uniform(-0.55, 0.5),
                    ru=rng.uniform(0.030, 0.055) + share * 0.03,
                    rv=rng.uniform(0.30, 0.55),
                    seed=seed + rng.randrange(1, 10_000),
                    wobble=0.55,
                )
            )
        return blobs

    count = 1 if share < 0.3 else 2 if share < 0.62 else 3
    blobs = []
    for index in range(count):
        # the first patch sits high on the back, the way kohaku is patterned
        v_center = rng.uniform(-0.6, 0.0) if index == 0 else rng.uniform(-0.35, 0.45)
        blobs.append(
            Blob(
                u=rng.uniform(0.2, 0.9),
                v=v_center,
                ru=0.085 + 0.145 * math.sqrt(min(share, 0.5)) + rng.uniform(-0.015, 0.025),
                rv=0.38 + 0.30 * min(share, 0.5) + rng.uniform(-0.06, 0.06),
                seed=seed + rng.randrange(1, 10_000),
                wobble=0.5,
            )
        )
    return blobs


def build_coat(
    *,
    body: str = "white",
    languages: list[dict] | None = None,
    identity_seed: int = 0,
    streak_longest: int = 0,
    total_contributions: int = 0,
) -> Coat:
    """Derive the coat: body ramp, pigment patches, and fin tint."""
    body = body if body in BODY_RAMPS else "white"
    rng = random.Random((identity_seed * 31 + 17) & 0xFFFFFFFF)

    counts: dict[str, float] = {}
    for language in languages or []:
        pigment = pigment_for_language(language.get("name"), language.get("color"))
        counts[pigment] = counts.get(pigment, 0.0) + float(language.get("count", 1))
    total = sum(counts.values())

    patterns: list[tuple[str, list[Blob]]] = []
    if total > 0:
        ordered = sorted(counts.items(), key=lambda item: -item[1])
        for pigment, count in ordered[:3]:
            share = count / total
            if share < 0.06:
                continue
            patterns.append(
                (pigment, _pattern_blobs(rng, pigment, share, identity_seed + len(patterns) * 101))
            )

    # a long streak gilds the fins
    if streak_longest >= 30:
        fin = FIN_RAMPS["gold"]
    elif streak_longest >= 14:
        fin = FIN_RAMPS["pale"]
    elif body in ("black", "asagi"):
        fin = FIN_RAMPS["smoke"]
    else:
        fin = FIN_RAMPS["pale"]

    return Coat(
        body=body,
        ramp=list(BODY_RAMPS[body]),
        fin_ramp=list(fin),
        patterns=patterns,
        net=body == "asagi",
        seed=identity_seed,
    )


def describe_coat(coat: Coat) -> str:
    names = ", ".join(pigment for pigment, _ in coat.patterns) or "plain"
    return f"{coat.body} body, {names} markings"


# --- water ----------------------------------------------------------------

WATER = (24, 78, 140)


def apply_depth(
    color: tuple[int, int, int], depth: float
) -> tuple[int, int, int]:
    """Sink a colour into the water; deeper koi read bluer and dimmer."""
    if depth <= 0:
        return color
    tinted = mix(color, WATER, depth * 0.45)
    return adjust(tinted, 1 - depth * 0.35, 1 - depth * 0.18)
