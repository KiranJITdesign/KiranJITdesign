# HOW TO — put an activity koi on your profile

This walks through the whole build, from an empty profile repository to a fish
that redraws itself every night. Read part 1 once, then keep part 4 for
reference.

---

## 0. What the original does, in one paragraph

The repo you linked, `yalongwastaken/yalongwastaken`, is a *profile repository*:
GitHub renders its `README.md` at the top of your profile page. Its workflows
run on a schedule, draw pictures, commit them back into the repo, and the README
shows those committed files. The koi itself lives in a separate repo,
`yalongwastaken/git-koi` — a Rust program, published both as a command line tool
and as a GitHub Action — which reads your public activity and renders a GIF.

So there are two ways to get the same result:

| Path | What you do | What you own |
| --- | --- | --- |
| **A. Use their Action** | add ~20 lines of YAML | nothing to maintain |
| **B. Own the code** (this zip) | copy this package in, edit Python | the whole generator |

Part 2 is path B, the code in this zip. Part 5 is path A, if you would rather
not maintain anything.

---

## 1. Prerequisites

- A GitHub account, and a repository named exactly after your username
  (`github.com/<you>/<you>`). If you do not have one: **New repository**, name
  it your username, tick **Add a README file**, create.
- Python 3.10+ locally, if you want to preview the fish before pushing.
- Nothing else. Pillow and NumPy are the only dependencies, and the workflow
  installs them.

---

## 2. Put the koi in your profile repository

### 2.1 Copy these files in

From this zip, copy into your profile repository:

```
koigen/                     the generator package
requirements.txt
.github/workflows/koi.yml   the nightly job
```

Commit and push.

### 2.2 Let the workflow push

**Settings → Actions → General → Workflow permissions** → select
**Read and write permissions** → Save.

Without this the drawing step works but the commit step is refused.

### 2.3 Run it once by hand

**Actions** tab → **Koi** in the sidebar → **Run workflow** → **Run workflow**.

Wait for the green tick. The run should end with a commit like
`koi: draw the day's koi`, and your repository should now contain:

```
koi/koi.gif         the loop, 256×256, 120 frames, 8 seconds
koi/koi.png         one still frame
koi/snapshot.json   the activity it was drawn from (handy for debugging)
```

### 2.4 Show it in your README

Add to `README.md`:

```html
<img src="koi/koi.gif" width="256" alt="My koi, redrawn every night from the day's activity">
```

`256` is exactly twice the koi's native 128-pixel canvas, so the pixels stay
crisp. Any other width will blur it.

### 2.5 Check it looks right

Open `koi/koi.gif` in the repo. If the fish is small, or the colours look
nothing like your languages, see part 4 and part 6.

---

## 3. How the code works

Five stages, each in its own file, each runnable on its own:

```
 GitHub API ──► snapshot.json ──► coat + anatomy ──► poses ──► frames ──► koi.gif
 collect.py     (plain JSON)      coat.py,           motion.py   render.py
                                  anatomy.py         behavior.py
```

**1. Collect (`collect.py`).** One GraphQL query fetches your contribution
calendar, your per-repository commit counts and each repository's primary
language. If GraphQL is unavailable it falls back to the REST API, which only
sees 90 days of public events — good enough to draw, not exact.

The result is a small JSON document:

```json
{
  "login": "you",
  "id": 123456789,
  "total_contributions": 1092,
  "days": [{"date": "2025-11-07", "count": 4}, "..."],
  "languages": [{"name": "Python", "color": "#3572A5", "count": 14}],
  "streak": {"longest": 27, "current": 3}
}
```

Everything after this stage is a pure function of that file, which is why
`--snapshot` can redraw a koi with no network at all.

**2. Grow and colour (`anatomy.py`, `coat.py`).** Total contributions map
through a log curve to a growth fraction, which sets body length, half-height,
eye size and fin length. Languages become eight possible pigments by hue;
each pigment's share decides how many organic patches it paints, placed from a
seed derived from your account id — so your fish is stable from night to night.
A streak of 30+ days gilds the fins.

**3. Choose the movement (`behavior.py`).** Deep rest, rest, surface feeding,
dart or cruise, in that order of priority, from quiet days, the first commit of
the week, milestone crossings and unusually busy weeks.

**4. Pose (`motion.py`).** Every frame is a `Pose`: heading, position, depth,
spine wave phase and strength, tail spread, pectoral opening, mouth opening,
whisker sway. A cruise is one lap in 120 frames with two strokes; a dart is two
laps with four bursts; rest and feeding hover in place. Every loop holds whole
numbers of laps, waves, beats and breaths, so it closes seamlessly.

**5. Draw (`render.py`).** Each pixel is transformed into the koi's own
coordinates — that is why a swimming lap never resamples a sprite. The body is a
spine curve with a half-height, sampled from a profile table; the fins are
shapes hanging off it; the coat decides the colour. Then a one-pixel outline is
dilated around the silhouette, depth tints the colours toward water blue, and
the frames are quantised to one shared 255-colour palette and written as a GIF
with hard transparency.

---

## 4. Customising

Everything is a flag on the command line, and a matching input in the workflow.

| Flag | Default | Effect |
| --- | --- | --- |
| `--login` | — | Account to draw |
| `--snapshot` | — | Draw from a saved JSON instead of the network |
| `--body` | `white` | `white`, `black`, `asagi`, `tea`, `gold`, `platinum` |
| `--out` | `koi` | Output folder |
| `--size` | `128` | Native canvas in pixels (raise to 192 for a bigger fish) |
| `--scale` | `2` | Export multiplier; `--size 128 --scale 2` gives 256×256 |
| `--frames` | all | Limit frames, for quick experiments |
| `--save-snapshot` | off | Keep the collected JSON |
| `--print-summary` | off | Print what the fish was drawn from |

In `.github/workflows/koi.yml`, change the `--body` value, or add
`--size 192 --scale 2`.

Other things worth touching:

- **Schedule.** `cron: "20 0 * * *"` is 00:20 UTC. For IST mornings, `"20 18 * * *"`.
- **Which languages count.** In `collect.py`, the loop over
  `commitContributionsByRepository` skips forks; drop that `if` to count them.
- **Palette.** `BODY_RAMPS` and `PIGMENT_RAMPS` at the top of `coat.py` are
  plain RGB lists. Light to dark, four steps for bodies, three for pigments.
- **Shape.** `_PROFILE` in `anatomy.py` is `(distance from snout, half-height)`
  pairs. Move a number and the silhouette changes.
- **Motion.** `CRUISE` / `DART` / `REST` in `behavior.py` set frame count, depth,
  speed and lap count.

Preview locally without touching GitHub:

```bash
python -m pip install -r requirements.txt
python -m koigen --snapshot examples/sample-snapshot.json --body gold --frames 20 --out /tmp/koi
```

---

## 5. The zero-code path, and the rest of the profile

The original is a published Action. If you would rather not own any code, put
this in `.github/workflows/koi.yml` instead:

```yaml
name: Koi
on:
  schedule: [{cron: "20 0 * * *"}]
  workflow_dispatch:
permissions:
  contents: write
concurrency: koi
jobs:
  koi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: yalongwastaken/git-koi@v1
        with:
          body: white
          output-dir: koi
      - run: |
          git add koi/koi.gif
          git diff --cached --quiet && exit 0
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git commit -m "koi: draw the day's koi"
          git push
```

The profile repo also carries two more nightly pictures. Both are included here
and both are other people's work, wired up the way the original repo wires them:

- **`bonsai.yml`** — `egorthinks/git-bonsai` grows a tree from your activity,
  then `scripts/recolor.py` swaps its palette for a comet-night one before the
  commit. Pin the action to a commit SHA, as the original does, or the colours
  will drift when upstream changes its palette slots.
- **`cards.yml`** — `stats-organization/github-readme-stats-action` writes the
  stats and language cards as SVG, once light and once dark, so the README can
  follow the reader's colour scheme with `<picture>`.

`README.template.md` in this zip is the profile README layout: koi on one side,
bonsai on the other, cards underneath.

---

## 6. Troubleshooting

**The workflow fails at "Draw the koi" with a 401 or "no such account".**
The built-in `GITHUB_TOKEN` can read public data. If your contributions are all
private, add a personal access token with `read:user` as a repository secret
(for example `KOI_TOKEN`) and pass it:
`env: { GITHUB_TOKEN: ${{ secrets.KOI_TOKEN }} }`.

**The GIF is drawn but nothing is committed.** Workflow permissions are still
read-only — see 2.2.

**The GIF on my profile did not change.** GitHub caches images through its camo
proxy. The new commit changes the file, so the cache refreshes within a few
minutes. Hard-refresh the profile page.

**The fish is tiny.** The total being read is the last year of contributions, not
an all-time total, so a quiet year draws a young fish. Either pass
`--size 160` for a bigger canvas, or lower `CONTRIBUTION_SCALE` in
`anatomy.py` so the growth curve saturates sooner.

**The fish is nearly all one colour.** That is the data: one language dominates
your commits. `PATCH_COVERAGE`-style knobs live in `_pattern_blobs` in
`coat.py` — shrink `ru`/`rv` there to leave more body showing.

**Colors look banded.** GIF allows 256 colours per frame and the encoder shares
one palette across all 120 frames. Fewer colours, smaller file; more, larger.
`save_gif` in `render.py` is where the quantiser is chosen.

**It is slow.** 120 frames at 128×128 takes about five seconds. `--frames 40`
for experiments; the workflow has no reason to.

---

## 7. Licence and credit

`git-koi` is MIT, © Anthony Yalong. This Python package is an independent
rewrite of that design and is MIT too; keep the attribution in `LICENSE` if you
publish your version.
