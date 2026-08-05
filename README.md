# substack

A toolkit for running and growing a Substack publication.

One CLI, no dependencies, no API keys, nothing scraped. Python 3.8+ standard
library only.

**Start with [PLAYBOOK.md](PLAYBOOK.md)** — that's the strategy. This file is the
manual.

```bash
./substack.py plan        # what to do today
./substack.py --help      # everything
```

## Setup

```bash
./substack.py init --publication "Your Publication" --author "Your Name" --stage prelaunch
./substack.py pos worksheet     # fill in positioning.md
./substack.py pos build         # → drafts/about.md + drafts/welcome-post.md
```

## The five tools

### `pos` — positioning
Finds the throughline for a personality-led publication, then generates the
About page, the pinned welcome post, and your profile bio from it.

```bash
./substack.py pos worksheet          # writes positioning.md
./substack.py pos build              # generates the assets
./substack.py pos check              # stress-tests legibility
```

### `notes` — the Notes engine
Notes drive most subscriber growth on Substack now, and the 2026 algorithm
weights *replies* and *restacks-with-commentary* above your own posting. So this
tracks all three, in ratio.

```bash
./substack.py notes hooks                        # 10 hook formulas + why each works
./substack.py notes draft "a raw thought"        # render it through all of them
./substack.py notes draft "idea" --hook contrarian --topic writing
./substack.py notes prompt "topic" -n 8          # LLM brief in your voice, ready to paste
./substack.py notes add "final text" --kind original --hook contrarian
./substack.py notes queue
./substack.py notes today                        # daily slate with progress bars
./substack.py notes done 3
./substack.py notes log                          # history + streak
```

**Close the loop.** Tag each note with the formula it used, score it a day or two
after posting, and the generic best-practice formulas become *your* data:

```bash
./substack.py notes score 3 --subs 6 --restacks 4 --replies 8 --likes 40
./substack.py notes tag 3 story                  # if you forgot to tag on add
./substack.py notes best                         # ranked by subscribers-per-note
```

`notes best` marks any formula with fewer than 3 scored notes as too thin to
trust, so you don't over-fit to one lucky post.

### `review` — the weekly loop
The only command that connects what you did to what happened. Run it the same
day every week.

```bash
./substack.py review           # last 7 days vs the 7 before
./substack.py review --days 30
```

Shows subscriber delta against the prior window, notes activity by kind, which
notes actually landed, what you published, network movement, and a read of the
week — plus three questions to answer before next week.

### `idea` / `post` — content pipeline
Idea bank → draft → pre-publish check → a week of Notes out of one essay.

```bash
./substack.py idea add "the thing you keep saying" --tag craft
./substack.py idea list
./substack.py idea promote 1                     # → a draft in drafts/
./substack.py post new "Working title"
./substack.py post list
./substack.py post check my-draft                # 8-point pre-publish checklist
./substack.py post repurpose my-draft --queue    # pull-quotes → notes queue
```

Drafts are plain markdown in `drafts/` with a structural template (hook / body /
turn / close). Paste into Substack when done.

### `net` — recommendation & cross-promo CRM
Recommendations compound; viral notes don't. This tracks the relationship through
`target → engaged → contacted → talking → partnered` and tells you who's going cold.

```bash
./substack.py net targets                        # where to find partners
./substack.py net add --name "Name" --publication "Pub" --topic writing --subs 5000
./substack.py net list
./substack.py net touch 1 --status contacted --note "sent the rec note"
./substack.py net due                            # who needs a nudge
./substack.py net template recommend --id 1 --specific "their post title"
```

### `stats` — analytics
Substack has no public API. Two honest data sources, both supported:

```bash
# 1. Log by hand — works from day zero, before you have any export
./substack.py stats log --subs 42 --followers 310 --views 900 --note "rec went live"

# 2. Official export — Substack → Settings → Exports → Create new export
./substack.py stats import ~/Downloads/export.zip

./substack.py stats show                         # terminal snapshot
./substack.py stats report                       # → data/report.html
```

The importer matches columns fuzzily (Substack has renamed them several times),
merges `posts.csv` with any stats export on title, and prints exactly which
columns it matched so you can see what it understood. The report is a
self-contained HTML file — inline SVG charts, light/dark aware, no external
requests.

### `plan` / `checklist` — the daily driver
```bash
./substack.py plan                               # stage-aware: what to do today
./substack.py checklist                          # 11-item launch checklist
./substack.py checklist --check welcome          # toggle an item
```

## Layout

```
substack.py          CLI entrypoint
sstools/             store, positioning, notes, pipeline, network, analytics, review, plan
tests/               regression suite — python3 -m unittest discover tests
data/                your JSON state (versioned — this is your backup)
data/exports/        raw Substack export zips            (gitignored — contains emails)
drafts/              your markdown drafts (versioned)
positioning.md       your worksheet (versioned)
PLAYBOOK.md          the strategy
```

### What's versioned, and why

Your idea bank, network CRM, metrics history, and drafts **are** committed. Six
months of relationship history and note scores exist nowhere else, and git is
the backup. The history is also useful on its own — `git log data/metrics.json`
shows how your growth actually unfolded.

**Only `data/exports/` is ignored**, because the raw export zips contain your
subscribers' email addresses. Note that `data/imported.json` is safe to commit:
the importer deliberately keeps signup date, paid status, and source, and drops
the email column entirely.

**If you ever make this repo public**, move `data/` and `drafts/` back into
`.gitignore` first, and check the history — committed data stays in git even
after you delete the files.

## Tests

```bash
python3 -m unittest discover tests        # 42 tests, no dependencies
```

The suite covers the parsing and aggregation logic — the parts that produce
*wrong answers* rather than crashing: fuzzy CSV column matching, the
posts/stats merge, date parsing across Substack's export formats, pull-quote
extraction, hook ranking, and review windowing. Every bug found while building
this is pinned here as a regression test.

## Note

Nothing here automates posting. Substack has no write API, and its 2026 ranking
is built specifically to reward genuine conversation — automated notes and
generic replies measurably underperform. These tools remove the friction around
the work; they don't do the work.
