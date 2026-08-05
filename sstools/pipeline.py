"""Content pipeline — idea bank → draft → pre-publish check → repurpose into Notes."""

import os
import re

from . import store
from .store import bold, bullet, dim, green, header, kv, magenta, ok, warn, yellow

POST_TEMPLATE = """---
title: {title}
subtitle:
date: {date}
status: draft
audience: everyone
section:
---

<!-- HOOK: first 2 lines decide whether the email gets read. No throat-clearing. -->


<!-- BODY -->


<!-- TURN: the paragraph where the reader's mind changes. Every essay needs one. -->


<!-- CLOSE: one question to the reader. Comments are a ranking signal AND your
     best source of the next three posts. -->

"""

CHECKS = [
    ("Does the first sentence work with zero context?",
     "Most readers meet you in an inbox preview or the app feed. No 'as I mentioned last week'."),
    ("Is the title a promise, not a label?",
     "'On Attention' is a label. 'You Are Not Distracted, You Are Avoiding Something' is a promise."),
    ("Is there one clear turn?",
     "The moment the reader's mind changes. If you can't point at it, the essay is a list of observations."),
    ("Did you cut the first paragraph?",
     "It is almost always warm-up. Try deleting it and see if anything is lost."),
    ("Is there a question at the end?",
     "Comments feed the algorithm and hand you your next three post ideas."),
    ("Have you pulled 3–5 Notes out of it?",
     "The post is the asset; Notes are the distribution. Run: ./substack.py post repurpose <file>"),
    ("Is there one restackable line?",
     "A single quotable sentence someone can screenshot. Write it on purpose."),
    ("Does it say something you'd defend out loud?",
     "Personality-led publications die of agreeableness."),
]


def _ideas():
    return store.load("ideas", {"items": []})


# --- idea bank --------------------------------------------------------------


def cmd_idea_add(args):
    data = _ideas()
    item = {
        "id": store.next_id(data["items"]),
        "text": args.text.strip(),
        "tag": args.tag or "",
        "created": store.today(),
        "status": "open",
    }
    data["items"].append(item)
    store.save("ideas", data)
    ok(f"idea #{item['id']} saved")
    return 0


def cmd_idea_list(args):
    items = [i for i in _ideas()["items"] if args.all or i["status"] == "open"]
    if not items:
        header("Idea bank")
        warn("empty — capture one:  ./substack.py idea add \"a thing you keep saying out loud\"")
        return 0
    header(f"Idea bank ({len(items)})")
    for i in items:
        tag = f" {dim('#' + i['tag'])}" if i["tag"] else ""
        mark = dim("·") if i["status"] == "open" else green("✓")
        print(f"  {mark} {bold('#' + str(i['id']))} {i['text'][:66]}{tag}")
    return 0


def cmd_idea_promote(args):
    data = _ideas()
    item = store.find(data["items"], args.id)
    if not item:
        store.err(f"no idea #{args.id}")
        return 1
    path = _new_draft(item["text"])
    item["status"] = "drafted"
    item["draft"] = os.path.basename(path)
    store.save("ideas", data)
    ok(f"promoted #{item['id']} → {path}")
    return 0


# --- drafts -----------------------------------------------------------------


def _new_draft(title):
    store.ensure_dirs()
    slug = store.slugify(title)
    path = os.path.join(store.DRAFTS, f"{store.today()}-{slug}.md")
    n = 2
    while os.path.exists(path):
        path = os.path.join(store.DRAFTS, f"{store.today()}-{slug}-{n}.md")
        n += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(POST_TEMPLATE.format(title=title, date=store.today()))
    return path


def cmd_post_new(args):
    path = _new_draft(args.title)
    ok(f"created {path}")
    bullet("Structure is in the comments — delete them as you fill each in.")
    return 0


def cmd_post_list(args):
    store.ensure_dirs()
    files = sorted(f for f in os.listdir(store.DRAFTS) if f.endswith(".md"))
    if not files:
        header("Drafts")
        warn("none yet:  ./substack.py post new \"Working title\"")
        return 0
    header(f"Drafts ({len(files)})")
    for f in files:
        path = os.path.join(store.DRAFTS, f)
        meta = _frontmatter(path)
        words = len(_body(path).split())
        status = meta.get("status", "draft")
        color = green if status == "published" else (yellow if words > 300 else dim)
        print(f"  {color(status.ljust(10))} {f.ljust(58)} {dim(str(words) + 'w')}")
    return 0


def _frontmatter(path):
    meta = {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta


def _body(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()


def _resolve(name):
    """Accept a bare filename, a partial match, or a full path."""
    if os.path.exists(name):
        return name
    store.ensure_dirs()
    cands = [f for f in os.listdir(store.DRAFTS) if name.lower() in f.lower()]
    if len(cands) == 1:
        return os.path.join(store.DRAFTS, cands[0])
    if not cands:
        store.err(f"no draft matching '{name}'")
    else:
        store.err(f"'{name}' matches {len(cands)}: " + ", ".join(cands[:5]))
    return None


def cmd_post_check(args):
    path = _resolve(args.file)
    if not path:
        return 1
    meta, body = _frontmatter(path), _body(path)
    words = len(body.split())
    header(f"Pre-publish — {os.path.basename(path)}")
    kv("title", meta.get("title", dim("(missing)")))
    kv("words", str(words))
    kv("read time", f"~{max(1, round(words / 220))} min")
    if words < 250:
        warn("under 250 words — fine for a note, thin for a post")
    print()
    for q, why in CHECKS:
        print(f"  {dim('☐')} {bold(q)}")
        print(store.wrap(dim(why), indent="      "))
    return 0


# --- repurpose --------------------------------------------------------------


def pull_quotes(body, limit=6, lo=40, hi=220):
    """Sentences that can stand alone as a Note.

    Headings and list markers are stripped first — otherwise a heading gets
    glued onto the sentence that follows it, since neither ends in punctuation.
    """
    prose = re.sub(r"^#{1,6}\s+.*$", "", body, flags=re.M)
    prose = re.sub(r"^\s*[-*>]\s+", "", prose, flags=re.M)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose.replace("\n", " "))
                 if s.strip()]
    return [s for s in sentences if lo <= len(s) <= hi][:limit]


def cmd_post_repurpose(args):
    path = _resolve(args.file)
    if not path:
        return 1
    body = _body(path)
    meta = _frontmatter(path)

    headings = re.findall(r"^#{1,4}\s+(.+)$", body, re.M)
    quotes = pull_quotes(body)

    header(f"Repurpose — {meta.get('title', os.path.basename(path))}")
    if not quotes and not headings:
        warn("draft is still empty — write the body first")
        return 0

    print(f"  {bold('Pull-quote notes')} {dim('(post these across the week, not the same day)')}")
    for i, qte in enumerate(quotes, 1):
        print(f"    {magenta(str(i) + '.')} {qte}")
    if headings:
        print()
        print(f"  {bold('Section hooks')} {dim('— each heading is a standalone note')}")
        for h in headings[:6]:
            bullet(h)

    print()
    print(f"  {bold('Sequence')}")
    bullet("Day 0  — publish the post, then post ONE note that is not a summary.")
    bullet("Day 1  — pull-quote note, no link. Let it live as its own idea.")
    bullet("Day 3  — the counter-argument you cut from the draft.")
    bullet("Day 5  — restack your own post with a new angle in the commentary.")
    bullet("Day 7  — a question the post raised but did not answer.")

    if args.queue:
        q = store.load("notes_queue", {"items": [], "log": []})
        for qte in quotes:
            q["items"].append({
                "id": store.next_id(q["items"]),
                "text": qte,
                "kind": "original",
                "target": os.path.basename(path),
                "created": store.today(),
                "status": "queued",
            })
        store.save("notes_queue", q)
        print()
        ok(f"queued {len(quotes)} notes")
    else:
        print()
        print(dim("  Add --queue to push these into the notes queue."))
    return 0


def register(sub):
    i = sub.add_parser("idea", help="idea bank")
    si = i.add_subparsers(dest="idea_cmd", required=True)
    ia = si.add_parser("add")
    ia.add_argument("text")
    ia.add_argument("--tag")
    ia.set_defaults(func=cmd_idea_add)
    il = si.add_parser("list")
    il.add_argument("--all", action="store_true")
    il.set_defaults(func=cmd_idea_list)
    ip = si.add_parser("promote", help="turn an idea into a draft")
    ip.add_argument("id")
    ip.set_defaults(func=cmd_idea_promote)

    p = sub.add_parser("post", help="drafts: new, list, check, repurpose")
    sp = p.add_subparsers(dest="post_cmd", required=True)
    pn = sp.add_parser("new")
    pn.add_argument("title")
    pn.set_defaults(func=cmd_post_new)
    sp.add_parser("list").set_defaults(func=cmd_post_list)
    pc = sp.add_parser("check", help="pre-publish checklist")
    pc.add_argument("file")
    pc.set_defaults(func=cmd_post_check)
    praw = sp.add_parser("repurpose", help="extract Notes from a draft")
    praw.add_argument("file")
    praw.add_argument("--queue", action="store_true", help="push pull-quotes into the notes queue")
    praw.set_defaults(func=cmd_post_repurpose)
