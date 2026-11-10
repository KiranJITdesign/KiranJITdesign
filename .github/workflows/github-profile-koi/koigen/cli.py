"""Command line: collect an account, draw its koi, write the loop."""

from __future__ import annotations

import argparse
import json
import os
import sys

from PIL import Image

from .anatomy import build_anatomy
from .behavior import select_behavior
from .coat import BODY_NAMES, build_coat, describe_coat
from .collect import collect
from .motion import FRAMES_PER_SECOND, Pose, build_poses
from .render import render_frame, save_gif

NATIVE_SIZE = 128
EXPORT_SCALE = 2


def _load_snapshot(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build(
    snapshot: dict,
    body: str = "white",
    size: int = NATIVE_SIZE,
    scale: int = EXPORT_SCALE,
    frame_limit: int | None = None,
) -> tuple[list[Image.Image], dict]:
    anatomy = build_anatomy(int(snapshot.get("total_contributions", 0)))
    behavior = select_behavior(snapshot)
    coat = build_coat(
        body=body,
        languages=snapshot.get("languages") or [],
        identity_seed=int(snapshot.get("id", 0)),
        streak_longest=int((snapshot.get("streak") or {}).get("longest", 0)),
        total_contributions=int(snapshot.get("total_contributions", 0)),
    )
    poses = build_poses(behavior, size, anatomy.growth)
    if frame_limit:
        poses = poses[:frame_limit]

    frames = [render_frame(coat, anatomy, pose, size) for pose in poses]

    # a centred still, facing right, for the README and for previews
    still = render_frame(
        coat,
        anatomy,
        Pose(
            heading=0.0,
            center=(size / 2.0, size / 2.0),
            depth=behavior.depth,
            wave_phase=0.6,
            wave_strength=0.85,
            tail_spread=0.08,
            pectoral_open=(0.30, -0.18),
            mouth_open=0.15,
            whisker_sway=0.05,
            bob=0.0,
        ),
        size,
    )
    if scale != 1:
        frames = [
            frame.resize((size * scale, size * scale), Image.NEAREST) for frame in frames
        ]
        still = still.resize((size * scale, size * scale), Image.NEAREST)
    summary = {
        "login": snapshot.get("login"),
        "body": body,
        "coat": describe_coat(coat),
        "growth": round(anatomy.growth, 3),
        "behavior": behavior.name,
        "frames": len(frames),
        "fps": FRAMES_PER_SECOND,
        "languages": [entry.get("name") for entry in (snapshot.get("languages") or [])][:5],
        "streak": snapshot.get("streak"),
        "total_contributions": snapshot.get("total_contributions"),
    }
    return frames, still, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="koigen",
        description="Draw a pixel-art koi from a GitHub account's public activity.",
    )
    parser.add_argument("--login", help="GitHub account whose koi to draw")
    parser.add_argument(
        "--snapshot",
        help="Draw from a saved snapshot JSON instead of the network",
    )
    parser.add_argument(
        "--save-snapshot",
        help="Write the collected snapshot to this path",
    )
    parser.add_argument(
        "--body",
        default="white",
        choices=list(BODY_NAMES),
        help="Body colour (default: white)",
    )
    parser.add_argument("--out", default="koi", help="Output folder (default: koi)")
    parser.add_argument("--size", type=int, default=NATIVE_SIZE, help="Native canvas size")
    parser.add_argument("--scale", type=int, default=EXPORT_SCALE, help="Export scale")
    parser.add_argument(
        "--frames", type=int, default=None, help="Limit the frame count (for quick tests)"
    )
    parser.add_argument("--token", default=None, help="GitHub token (defaults to GITHUB_TOKEN)")
    parser.add_argument("--print-summary", action="store_true", help="Print the summary as JSON")
    args = parser.parse_args(argv)

    if args.snapshot:
        snapshot = _load_snapshot(args.snapshot)
    elif args.login:
        snapshot = collect(args.login, args.token)
        if args.save_snapshot:
            with open(args.save_snapshot, "w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, indent=2)
    else:
        parser.error("give either --login or --snapshot")

    frames, still, summary = build(
        snapshot, body=args.body, size=args.size, scale=args.scale, frame_limit=args.frames
    )

    os.makedirs(args.out, exist_ok=True)
    gif_path = os.path.join(args.out, "koi.gif")
    save_gif(frames, gif_path, round(1000 / FRAMES_PER_SECOND))
    still.save(os.path.join(args.out, "koi.png"))

    if args.print_summary:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"{summary['login']}: {summary['coat']}, {summary['behavior']}, "
            f"{summary['frames']} frames -> {gif_path}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
