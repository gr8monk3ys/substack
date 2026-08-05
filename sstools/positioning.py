"""Positioning — find the throughline for a personality-led publication.

The hard problem with "I'm not picking a niche, I'm building a personality":
Substack's discovery surfaces are all *legibility* machines. A stranger scrolling
Notes gives you about two seconds. Recommendations ask another writer to explain
you to their readers in one line. Neither rewards "a bit of everything".

The resolution isn't a niche. It's a CONTAINER: a legible promise wide enough to
hold whatever you're interested in. Write Conscious is a personality brand — Ian
Cattanach is the draw — but it sits inside "literature and the writing life",
with named sections (Book Club, Writing School, the podcast). Wide inside,
legible outside.

    ./substack.py pos worksheet   → writes positioning.md for you to fill in
    ./substack.py pos build       → turns the filled worksheet into real assets
"""

import os
import re

from . import store
from .store import bold, bullet, dim, green, header, kv, ok, warn, yellow

WORKSHEET = """# Positioning worksheet

Fill in every line after the `:`. Keep answers short and concrete — vague answers
here produce vague assets. Then run: ./substack.py pos build

## Who
name:
one_sentence_bio:

## The three obsessions
Pick the three things you'd still be reading about if nobody was watching.
Not "what should I write about" — what you already can't stop thinking about.
obsession_1:
obsession_2:
obsession_3:

## The throughline
What do those three share? Not a topic — a QUESTION or a STANCE.
Bad:  "books, philosophy, and tech"
Good: "how people build an inner life in a world engineered to prevent it"
throughline:

## The container
The name of the shelf your work sits on. Two to four words a stranger
understands instantly. This is what other writers will say when they
recommend you.
container:

## The reader
Who is this for? One person, described specifically. Not a demographic.
reader:
what_they_want:
what_they_get_from_you:

## The promise
Finish this: "Every week I ___, so you can ___."
promise:

## Cadence
posting_day:
frequency:
format:

## Sections
Named containers inside the container — these become Substack sections.
Three is right. They let you be wide without looking scattered.
section_1:
section_2:
section_3:
"""


def _parse(path):
    fields = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^([a-z_0-9]+):\s*(.*)$", line.strip())
            if m:
                fields[m.group(1)] = m.group(2).strip()
    return fields


def _path():
    return os.path.join(store.ROOT, "positioning.md")


def _sent(text, period=True):
    """Worksheet answers get typed as fragments. Make them read as sentences."""
    s = str(text or "").strip()
    if not s:
        return s
    s = s[:1].upper() + s[1:]
    if period and s[-1] not in ".!?:":
        s += "."
    return s


def cmd_worksheet(args):
    path = _path()
    if os.path.exists(path) and not args.force:
        header("Worksheet")
        warn(f"{path} already exists — pass --force to overwrite it")
        filled = _parse(path)
        done = sum(1 for v in filled.values() if v)
        kv("filled in", f"{done}/{len(filled)} fields")
        return 0
    with open(path, "w", encoding="utf-8") as f:
        f.write(WORKSHEET)
    header("Worksheet")
    ok(f"wrote {path}")
    bullet("Fill it in, then run:  ./substack.py pos build")
    bullet(bold("Do the three-obsessions question honestly.") + " It's the whole exercise. "
           "A personality brand without a throughline reads as noise to a stranger.")
    return 0


def cmd_build(args):
    path = _path()
    if not os.path.exists(path):
        store.err("no positioning.md — run:  ./substack.py pos worksheet")
        return 1
    f = _parse(path)
    missing = [k for k in ("name", "throughline", "container", "reader", "promise")
               if not f.get(k)]
    if missing:
        header("Build")
        warn("fill these in first: " + ", ".join(missing))
        return 1

    store.set_config(
        author=f.get("name"),
        publication=f.get("container"),
        throughline=f.get("throughline"),
        post_day=f.get("posting_day") or None,
        cadence=f.get("frequency") or None,
    )

    sections = [f.get(f"section_{i}") for i in (1, 2, 3)]
    sections = [s for s in sections if s]
    obsessions = [f.get(f"obsession_{i}") for i in (1, 2, 3)]
    obsessions = [o for o in obsessions if o]

    obs_line = ("I write about " + ", ".join(obsessions[:-1]) + ", and " + obsessions[-1] + ". "
                if len(obsessions) > 2 else "")

    about = f"""# About {f['container']}

{_sent(f.get('one_sentence_bio', ''))}

**{_sent(f['throughline'])}**

## What this is

{_sent(f['promise'])}

{obs_line}Those look like different subjects. They're one subject: \
{f['throughline'].rstrip('.').lower()}.

## Who it's for

{_sent(f['reader'])}

You want {f.get('what_they_want', '—').rstrip('.')}. Here you get \
{f.get('what_they_get_from_you', '—').rstrip('.')}.

## What you'll get

{f.get('frequency', 'Weekly')} — {f.get('format', 'an essay')}, {f.get('posting_day', 'most weeks')}.

{chr(10).join('- **' + s + '**' for s in sections)}

## Start here

1. <!-- link your best post -->
2. <!-- link your second best -->
3. <!-- link the one that's most *you* -->

— {f['name']}
"""

    welcome = f"""---
title: Start here
subtitle: {_sent(f['throughline'], period=False)}
pinned: true
---

You've landed on {f['container']}. Here's the whole thing in thirty seconds.

**{_sent(f['promise'])}**

I'm {f['name']}. {_sent(f.get('one_sentence_bio', ''))}

I write about {', '.join(obsessions) if obsessions else '—'}. If that sounds
scattered, it isn't: {f['throughline'].rstrip('.').lower()}.

## Who this is for

{_sent(f['reader'])}

## What to expect

{f.get('frequency', 'Weekly')}, {f.get('posting_day', '')}. {f.get('format', 'An essay')}.

{chr(10).join('- **' + s + '**' for s in sections)}

## The deal

I'll never send you filler. If I don't have something worth your inbox, I won't send.

Subscribe below and the next one comes to you.

<!-- SUBSCRIBE BUTTON -->

— {f['name']}
"""

    tl = f["throughline"].strip()
    bio = f"{f.get('one_sentence_bio', '')} {tl[:1].upper() + tl[1:]}".strip()

    out = {}
    for name, content in (("about.md", about), ("welcome-post.md", welcome)):
        p = os.path.join(store.DRAFTS, name)
        store.ensure_dirs()
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        out[name] = p

    header("Built")
    for name, p in out.items():
        ok(p)
    print()
    kv("publication", f["container"])
    kv("throughline", f["throughline"])
    print()
    print(f"  {bold('Substack bio')} {dim('(paste into your Substack profile)')}")
    print(store.wrap(bio, indent="    "))
    print()
    if len(bio) > 200:
        warn(f"bio is {len(bio)} chars — cut it under ~160 so it doesn't truncate")
    if sections:
        print(f"  {bold('Create these as Substack sections')} {dim('(Settings → Sections)')}")
        for s in sections:
            bullet(s)
    else:
        warn("no sections defined — three named sections is how you stay wide without looking scattered")
    return 0


def cmd_check(args):
    """Stress-test the positioning against how strangers actually encounter you."""
    cfg = store.config()
    header("Legibility check")
    tests = [
        ("The two-second test",
         "A stranger sees one of your notes in a feed full of strangers. From that note alone, "
         "can they tell what following you gets them?",
         bool(cfg.get("throughline"))),
        ("The recommendation test",
         "Another writer wants to recommend you. They have one sentence. Can they write it "
         "without asking you what you're about?",
         bool(cfg.get("publication") and cfg.get("throughline"))),
        ("The third-post test",
         "Someone reads three of your posts on three different subjects. Do they feel one mind "
         "at work, or three?",
         bool(cfg.get("throughline"))),
        ("The scale test",
         "Can this container still hold you at 10,000 subscribers, or will you have outgrown "
         "the promise? Narrow enough to be legible, wide enough to last.",
         bool(cfg.get("publication"))),
    ]
    for name, q, passed in tests:
        mark = green("✓") if passed else yellow("○")
        print(f"  {mark} {bold(name)}")
        print(store.wrap(dim(q), indent="      "))
        print()
    if not cfg.get("throughline"):
        warn("no throughline set — run:  ./substack.py pos worksheet")
    return 0


def register(sub):
    p = sub.add_parser("pos", help="positioning: throughline, about page, welcome post")
    s = p.add_subparsers(dest="pos_cmd", required=True)
    w = s.add_parser("worksheet", help="write positioning.md")
    w.add_argument("--force", action="store_true")
    w.set_defaults(func=cmd_worksheet)
    s.add_parser("build", help="generate about page + welcome post from the worksheet") \
        .set_defaults(func=cmd_build)
    s.add_parser("check", help="stress-test your positioning").set_defaults(func=cmd_check)
