"""A pixel-art koi drawn from a GitHub account's public activity."""

from .anatomy import build_anatomy, growth_fraction
from .behavior import select_behavior
from .coat import BODY_NAMES, build_coat
from .collect import collect
from .render import render_frame, save_gif

__all__ = [
    "BODY_NAMES",
    "build_anatomy",
    "build_coat",
    "collect",
    "growth_fraction",
    "render_frame",
    "save_gif",
    "select_behavior",
]
__version__ = "1.0.0"
