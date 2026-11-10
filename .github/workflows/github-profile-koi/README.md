# Koi — a pixel-art fish grown from your GitHub activity

Your languages colour it, your contributions grow it, your streaks tint its
fins, and the day that just ended decides how it swims. A nightly workflow
redraws it as a looping GIF in your profile README.

This is a self-contained Python implementation of the idea behind
[`yalongwastaken/git-koi`](https://github.com/yalongwastaken/git-koi) (Rust,
MIT). No Rust toolchain, no compiled binary: one `pip install`, one command,
one GIF.

```
                    ,-.        <- dorsal fin
        ___        /   \       <- body, painted from your languages
   \___/   \______/     \      <- eye, whiskers
       \___/  \_________/      <- tail, gilded by a long streak
```

## Quick start

```bash
python -m pip install -r requirements.txt

# draw from a live account (needs a token for the contribution calendar)
GITHUB_TOKEN=ghp_xxx python -m koigen --login your-username --out koi

# or draw from a saved snapshot, no network at all
python -m koigen --snapshot examples/sample-snapshot.json --out koi
```

You get `koi/koi.gif` (256×256, 120 frames, 8 second loop) and `koi/koi.png`.

## What drives the fish

| Your activity | What it changes |
| --- | --- |
| Total contributions | Size, from a fry to a full-grown koi |
| Languages (by commit count) | The coloured patches on the body |
| Longest streak | The tint of the fins |
| Quiet days | The koi rests, sinks, and barely moves |
| A busy week, or crossing 1k / 5k / 10k … | It darts, two fast laps instead of one |
| First commit of the week | It feeds at the surface and gulps |

## Bodies

`--body white | black | asagi | tea | gold | platinum`

## Files

```
koigen/          the generator
  collect.py     GitHub -> snapshot JSON (GraphQL, REST fallback)
  coat.py        bodies, pigments, patches, palettes
  anatomy.py     growth curve and body proportions
  motion.py      poses: laps, hovers, fin beats, breaths
  behavior.py    which movement today gets
  render.py      draws a frame, encodes the loop
  cli.py         the command line
.github/workflows/   nightly koi, bonsai and stats-card workflows
scripts/recolor.py   comet-night palette for git-bonsai (from the profile repo)
examples/            a sample snapshot to render offline
```

## Credit

The design — growth from contribution totals, language pigments, streak marks,
behaviour chosen by recent activity, a seamless 15 fps loop — is Anthony
Yalong's, from `git-koi`. This implementation is an independent Python rewrite
of that design, released under the MIT licence like the original. If you want
the original, it is a GitHub Action: `uses: yalongwastaken/git-koi@v1`.
