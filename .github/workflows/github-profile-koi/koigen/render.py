"""Render one frame of the koi, and encode the loop.

The whole frame is drawn as a field: every pixel is transformed into the koi's
own coordinates, where the body is a curve with a half-height, the fins are
shapes hanging off it, and the coat decides the colour. That keeps the rotation
of a swimming lap clean, with no resampling of an already-drawn sprite.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from .anatomy import Anatomy, _PROFILE
from .coat import (
    OUTLINE,
    PIGMENT_RAMPS,
    Coat,
    apply_depth,
    mix,
)

_PROFILE_S = np.array([point[0] for point in _PROFILE])
_PROFILE_H = np.array([point[1] for point in _PROFILE])

TAIL_SPREAD = 0.72  # radians either side of the tail's axis
TAIL_LENGTH = 0.40  # of body length, at full growth
PECTORAL_LENGTH = 0.24
PECTORAL_HALF_WIDTH = 0.095
DORSAL_RANGE = (0.26, 0.62)
ANAL_RANGE = (0.15, 0.30)
WHISKER_LENGTH = 0.07


def _grid(size: int) -> tuple[np.ndarray, np.ndarray]:
    axis = np.arange(size, dtype=np.float64) + 0.5
    return np.meshgrid(axis, axis, indexing="xy")


def _segment_distance(
    px: np.ndarray, py: np.ndarray, ax: float, ay: float, bx: float, by: float
) -> np.ndarray:
    abx, aby = bx - ax, by - ay
    length_squared = abx * abx + aby * aby
    if length_squared == 0:
        return np.hypot(px - ax, py - ay)
    t = ((px - ax) * abx + (py - ay) * aby) / length_squared
    t = np.clip(t, 0.0, 1.0)
    return np.hypot(px - (ax + abx * t), py - (ay + aby * t))


def _shade_index(v: np.ndarray, steps: int) -> np.ndarray:
    index = np.zeros(v.shape, dtype=np.int32)
    index[v >= -0.62] = 1
    index[v >= 0.18] = 2
    index[v >= 0.72] = 3
    return np.clip(index, 0, steps - 1)


def _fin_rays(across: np.ndarray, span: float, count: int) -> np.ndarray:
    return (np.floor((across / span + 1.0) * 0.5 * count) % 2) == 0


def render_frame(
    coat: Coat, anat: Anatomy, pose, size: int
) -> Image.Image:
    xs, ys = _grid(size)
    length = anat.length
    half = length / 2.0
    cos_h, sin_h = math.cos(pose.heading), math.sin(pose.heading)

    dx = xs - pose.center[0]
    dy = ys - pose.center[1]
    lx = dx * cos_h + dy * sin_h
    ly = -dx * sin_h + dy * cos_h

    u = np.clip((lx + half) / length, 0.0, 1.0)
    body_reach = (lx >= -half) & (lx <= half)

    spine = (
        length
        * 0.045
        * np.power(np.clip(1.0 - u, 0.0, 1.0), 1.7)
        * pose.wave_strength
        * np.sin(2 * math.pi * (0.9 * u) + pose.wave_phase)
    )
    height = anat.half_height * np.interp(1.0 - u, _PROFILE_S, _PROFILE_H)
    v = (ly - spine) / np.maximum(height, 1e-6)

    body = body_reach & (np.abs(v) <= 1.0)

    def spine_at(uu: float) -> float:
        return (
            length
            * 0.045
            * ((1.0 - uu) ** 1.7)
            * pose.wave_strength
            * math.sin(2 * math.pi * 0.9 * uu + pose.wave_phase)
        )

    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    filled = np.zeros((size, size), dtype=bool)

    # --- body ---------------------------------------------------------------
    ramp = np.array(coat.ramp, dtype=np.uint8)
    shade = _shade_index(v, len(coat.ramp))
    body_color = ramp[shade]
    rgb[body] = body_color[body]
    filled |= body

    # pigment patches, painted on the body only
    for pigment, blobs in coat.patterns:
        mask = np.zeros((size, size), dtype=bool)
        for blob in blobs:
            shear = 0.18 * np.sin((v - blob.v) * 3.1 + (blob.seed % 13))
            du = (u - blob.u + shear) / blob.ru
            dv = (v - blob.v) / blob.rv
            phase = (blob.seed % 97) * 0.13
            angle = np.arctan2(dv, du)
            edge = (
                1.0
                + 0.13 * np.sin(angle * 3.0 + phase)
                + 0.08 * np.sin(angle * 5.0 - phase * 1.3)
                + 0.05 * np.sin((u + v) * 61.0 + phase * 2.3)
            )
            mask |= (du * du + dv * dv) <= edge
        mask &= body
        if not mask.any():
            continue
        pigment_ramp = np.array(PIGMENT_RAMPS[pigment], dtype=np.uint8)
        pigment_shade = np.clip(shade, 0, len(pigment_ramp) - 1)
        rgb[mask] = pigment_ramp[pigment_shade][mask]

    # the scale net of an Asagi
    if coat.net:
        net = (
            ((np.floor(u * 22) + np.floor(v * 12)) % 2 == 0)
            & body
            & (v < -0.25)
        )
        rgb[net] = np.array(coat.net_color, dtype=np.uint8)

    # a glint along the shoulder
    glint = (
        body
        & (u > 0.40)
        & (u < 0.62)
        & (v > -0.85)
        & (v < -0.55)
        & (np.sin(u * 90.0) > 0.55)
    )
    rgb[glint] = (255, 255, 255)

    # --- fins ---------------------------------------------------------------
    fin_ramp = np.array(coat.fin_ramp, dtype=np.uint8)
    fin_scale = anat.fin_scale

    def paint(mask: np.ndarray, base_index: int, ray_mask: np.ndarray | None = None) -> None:
        nonlocal filled
        if not mask.any():
            return
        colors = np.zeros((size, size, 3), dtype=np.uint8)
        colors[:, :] = fin_ramp[min(base_index, len(fin_ramp) - 1)]
        if ray_mask is not None:
            rays = mask & ray_mask
            colors[rays] = fin_ramp[-1]
        rgb[mask] = colors[mask]
        filled |= mask

    # caudal fin
    tail_angle = anat.tail_angle(pose.wave_phase, pose.wave_strength) + pose.tail_spread
    root_x = -half + 0.015 * length
    root_y = float(
        length * 0.045 * pose.wave_strength * math.sin(pose.wave_phase)
    )
    dir_x, dir_y = -math.cos(tail_angle), -math.sin(tail_angle)
    rx, ry = lx - root_x, ly - root_y
    dot = rx * dir_x + ry * dir_y
    cross = dir_x * ry - dir_y * rx
    theta = np.arctan2(cross, dot)
    reach = np.hypot(rx, ry)
    tail_length = length * TAIL_LENGTH * fin_scale
    spread = np.clip(np.abs(theta) / TAIL_SPREAD, 0.0, 1.0)
    limit = tail_length * (0.42 + 0.58 * np.power(spread, 0.85))
    tail = (
        (np.abs(theta) <= TAIL_SPREAD)
        & (reach <= limit)
        & ~body
    )
    tail_rays = _fin_rays(theta / TAIL_SPREAD, 1.0, 9) & (reach > limit * 0.25)
    paint(tail, 1, tail_rays)

    # dorsal fin
    dorsal_low, dorsal_high = DORSAL_RANGE
    dorsal_span = (u >= dorsal_low) & (u <= dorsal_high) & body_reach
    dorsal_rise = (
        length
        * 0.085
        * fin_scale
        * np.power(
            np.clip(
                np.sin(math.pi * (u - dorsal_low) / (dorsal_high - dorsal_low)), 0.0, 1.0
            ),
            1.3,
        )
    )
    back = spine - height
    dorsal = dorsal_span & (ly <= back + 0.4) & (ly >= back - dorsal_rise) & ~body
    dorsal_rays = _fin_rays(u - dorsal_low, dorsal_high - dorsal_low, 7)
    paint(dorsal, 1, dorsal_rays)

    # anal fin
    anal_low, anal_high = ANAL_RANGE
    anal_span = (u >= anal_low) & (u <= anal_high) & body_reach
    anal_drop = (
        length
        * 0.09
        * fin_scale
        * np.power(
            np.clip(
                np.sin(math.pi * (u - anal_low) / (anal_high - anal_low)), 0.0, 1.0
            ),
            0.7,
        )
    )
    belly = spine + height
    anal = anal_span & (ly >= belly - 0.4) & (ly <= belly + anal_drop) & ~body
    paint(anal, 1, _fin_rays(u - anal_low, anal_high - anal_low, 5))

    # pectoral fin, beating
    pectoral_u = 0.74
    root_px = -half + pectoral_u * length
    root_py = spine_at(pectoral_u) + 0.80 * anat.half_height_at(pectoral_u)
    pectoral_angle = math.pi + 0.38 + pose.pectoral_open[0]
    pdx, pdy = math.cos(pectoral_angle), math.sin(pectoral_angle)
    prx, pry = lx - root_px, ly - root_py
    along = prx * pdx + pry * pdy
    across = -prx * pdy + pry * pdx
    plen = length * PECTORAL_LENGTH * fin_scale
    phalf = length * PECTORAL_HALF_WIDTH * fin_scale
    pectoral = (
        (along >= 0.0)
        & ((along / plen) ** 2 + (across / phalf) ** 2 <= 1.0)
        & ~body
    )
    paint(pectoral, 1, _fin_rays(across, phalf, 5))

    # pelvic fin, small and trailing
    pelvic_u = 0.56
    pelvic_px = -half + pelvic_u * length
    pelvic_py = spine_at(pelvic_u) + 0.95 * anat.half_height_at(pelvic_u)
    pelvic_angle = math.pi + 0.85 + 0.35 * pose.pectoral_open[1]
    vdx, vdy = math.cos(pelvic_angle), math.sin(pelvic_angle)
    vrx, vry = lx - pelvic_px, ly - pelvic_py
    v_along = vrx * vdx + vry * vdy
    v_across = -vrx * vdy + vry * vdx
    vlen = plen * 0.55
    vhalf = phalf * 0.62
    pelvic = (
        (v_along >= 0.0)
        & ((v_along / vlen) ** 2 + (v_across / vhalf) ** 2 <= 1.0)
        & ~body
    )
    paint(pelvic, 1, _fin_rays(v_across, vhalf, 3))

    # --- face ---------------------------------------------------------------
    eye_u, eye_v = 0.885, -0.26
    eye_x = -half + eye_u * length
    eye_y = spine_at(eye_u) - eye_v * anat.half_height_at(eye_u)
    eye_r = anat.eye_radius
    eye = np.hypot(lx - eye_x, ly - eye_y) <= eye_r
    rgb[eye] = (24, 20, 37)
    filled |= eye
    spark = np.hypot(lx - (eye_x - eye_r * 0.35), ly - (eye_y - eye_r * 0.35)) <= eye_r * 0.42
    rgb[spark & eye] = (255, 255, 255)

    # mouth, opening with the breath
    mouth_half = 0.10 + 0.22 * pose.mouth_open
    mouth = (
        body_reach
        & (u > 0.975)
        & (np.abs(v - (-0.02)) < mouth_half)
    )
    rgb[mouth] = (52, 32, 40)

    # whiskers, angling forward from the snout
    snout_x = half
    snout_y = spine_at(1.0)
    snout_h = anat.half_height_at(1.0)
    for side in (-1, 1):
        angle = side * (0.32 + pose.whisker_sway)
        tip_x = snout_x + math.cos(angle) * length * WHISKER_LENGTH
        tip_y = snout_y + side * snout_h * 0.35 + math.sin(angle) * length * WHISKER_LENGTH
        distance = _segment_distance(lx, ly, snout_x, snout_y + side * snout_h * 0.45, tip_x, tip_y)
        whisker = distance <= 0.45
        rgb[whisker] = np.array(coat.ramp[0], dtype=np.uint8)
        filled |= whisker

    # --- outline ------------------------------------------------------------
    grown = np.zeros_like(filled)
    grown[1:, :] |= filled[:-1, :]
    grown[:-1, :] |= filled[1:, :]
    grown[:, 1:] |= filled[:, :-1]
    grown[:, :-1] |= filled[:, 1:]
    edge = grown & ~filled
    rgb[edge] = OUTLINE
    filled |= edge

    # --- depth and export ---------------------------------------------------
    if pose.depth > 0:
        tinted = apply_depth_to_array(rgb, pose.depth)
        rgb = tinted

    alpha = np.where(filled, 255, 0).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])
    return Image.fromarray(rgba, mode="RGBA")


def apply_depth_to_array(rgb: np.ndarray, depth: float) -> np.ndarray:
    """Vectorised version of coat.apply_depth for a whole frame."""
    flat = rgb.reshape(-1, 3).astype(np.float64)
    tint = np.array((24, 78, 140), dtype=np.float64)
    blended = flat + (tint - flat) * (depth * 0.45)
    blended *= 1 - depth * 0.12
    return np.clip(blended, 0, 255).astype(np.uint8).reshape(rgb.shape)


def save_gif(frames: list[Image.Image], path: str, duration_ms: int) -> None:
    """Encode a seamless loop with one shared palette and hard transparency."""
    if not frames:
        raise ValueError("no frames to encode")
    width, height = frames[0].size
    montage = Image.new("RGB", (width, height * len(frames)))
    for index, frame in enumerate(frames):
        montage.paste(frame.convert("RGB"), (0, index * height))
    palette_image = montage.quantize(colors=255, method=Image.MEDIANCUT)

    encoded = []
    for frame in frames:
        flat = frame.convert("RGB").quantize(palette=palette_image, dither=Image.NONE)
        alpha = frame.getchannel("A").point(lambda value: 255 if value < 128 else 0)
        flat.paste(255, mask=alpha)
        flat.info["transparency"] = 255
        encoded.append(flat)

    encoded[0].save(
        path,
        save_all=True,
        append_images=encoded[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        transparency=255,
        optimize=False,
    )
