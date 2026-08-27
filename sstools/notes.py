"""Notes engine — hook formulas, a posting queue, and the daily engagement slate.

Notes are the primary discovery surface on Substack in 2026: the feed shows readers
mostly creators they do NOT follow, and high-signal replies/restacks outrank likes.
So this tool tracks three separate activities, not just "posting":

    originals  — your own notes
    replies    — substantive replies on other people's notes
    restacks   — restacks WITH commentary (the strongest shared-audience signal)
"""

from datetime import date, timedelta

from . import store
from .store import bold, bullet, dim, green, header, kv, magenta, ok, warn, yellow

# Hook formulas. Each renders a raw idea into a proven Notes structure.
# {idea} is the user's raw thought; {topic} a short subject if they gave one.
HOOKS = [
    {
        "key": "contrarian",
        "name": "Contrarian flip",
        "why": "Disagreement is the cheapest reply-bait that isn't cheap. Replies are the top-weighted signal.",
        "template": "Everyone tells you {topic} is about doing more.\n\nIt isn't.\n\n{idea}",
    },
    {
        "key": "confession",
        "name": "Confession",
        "why": "Personality brands run on disclosure. Vulnerability converts strangers into followers faster than expertise.",
        "template": "I'm going to admit something.\n\n{idea}\n\nNobody warns you about this part.",
    },
    {
        "key": "reframe",
        "name": "Definition reframe",
        "why": "Short, quotable, highly restackable. Restacks are what carry you into new audiences.",
        "template": "{topic} isn't what you think it is.\n\nIt's this: {idea}",
    },
    {
        "key": "list",
        "name": "Numbered beliefs",
        "why": "Scannable in the feed. Each line is an independent hook, so one of them lands.",
        "template": "Things I believe about {topic}:\n\n1. {idea}\n2. \n3. \n4. ",
    },
    {
        "key": "story",
        "name": "Micro-story",
        "why": "The single best format for a personality-led publication. Story > claim.",
        "template": "{idea}\n\nI think about that more than I should.",
    },
    {
        "key": "question",
        "name": "Open question",
        "why": "Directly manufactures replies. Ask something people already have an answer to.",
        "template": "{idea}\n\nWhat's yours? I read every reply.",
    },
    {
        "key": "receipts",
        "name": "Receipts",
        "why": "Concrete numbers stop the scroll and signal you actually did the thing.",
        "template": "{idea}\n\nHere's the number nobody shares:",
    },
    {
        "key": "beforeafter",
        "name": "Before / after",
        "why": "Transformation is the most legible payoff a stranger can grasp in two seconds.",
        "template": "A year ago: \n\nNow: \n\nThe difference was one thing — {idea}",
    },
    {
        "key": "commentary",
        "name": "Restack commentary",
        "why": "Restack + your own take. Tells the algorithm you and that writer share an audience.",
        "template": "[restack the post, then add:]\n\n{idea}\n\nThis is the part I'd underline.",
    },
    {
        "key": "unpopular",
        "name": "Permission slip",
        "why": "Giving readers permission to stop doing something is quietly the most shared note type.",
        "template": "You're allowed to stop {topic}.\n\n{idea}",
    },
]

KINDS = ("original", "reply", "restack")


def _queue():
    return store.load("notes_queue", {"items": [], "log": []})


def _save(q):
    store.save("notes_queue", q)


# --- commands ---------------------------------------------------------------


def cmd_hooks(args):
    header("Note hook formulas")
    for h in HOOKS:
        print(f"  {bold(h['key'].ljust(12))} {h['name']}")
        print(store.wrap(dim(h["why"]), indent="               "))
        print()
    print(dim("  Render one against your own idea:  ./substack.py notes draft \"your raw thought\""))


def cmd_draft(args):
    """Render a raw idea through every hook formula (or one named formula)."""
    idea = args.idea.strip()
    topic = (args.topic or "this").strip()
    picks = [h for h in HOOKS if h["key"] == args.hook] if args.hook else HOOKS
    if not picks:
        store.err(f"unknown hook '{args.hook}' — run: ./substack.py notes hooks")
        return 1

    picks = picks[: args.n] if args.n else picks
    header(f"{len(picks)} drafts from: {idea[:60]}")
    for h in picks:
        body = h["template"].format(idea=idea, topic=topic)
        print(f"  {magenta('┌')} {bold(h['name'])} {dim('(' + h['key'] + ')')}")
        for line in body.split("\n"):
            print(f"  {magenta('│')} {line}")
        print(f"  {magenta('└')}")
        print()
    print(dim("  Queue the one you like:  ./substack.py notes add \"<final text>\""))
    return 0


def cmd_prompt(args):
    """Emit a ready-to-paste LLM prompt for generating notes in the user's voice.

    This tool does not invent content for you — it builds the brief that gets
    good output out of whatever model you paste it into.
    """
    cfg = store.config()
    ideas = store.load("ideas", {"items": []})["items"]
    recent = [i["text"] for i in ideas[-8:]]

    print(f"""You are helping me write Substack Notes.

CONTEXT
- Publication: {cfg['publication'] or '(unnamed)'}
- Author: {cfg['author'] or '(me)'}
- Throughline: {cfg['throughline'] or '(not yet defined — infer it from my ideas below)'}
- Stage: {cfg['stage']} (so: assume readers have never heard of me)

MY RAW MATERIAL
{chr(10).join('- ' + t for t in recent) or '- (idea bank is empty)'}

TOPIC FOR THIS BATCH: {args.idea or '(pick from my raw material)'}

RULES
- Notes are short. 40-80 words. No preamble, no "In today's edition".
- First line must work alone as the whole hook — the feed truncates.
- Write like a person talking, not a brand publishing. Contractions. Short sentences.
- No hashtags, no emoji clusters, no "thread below".
- Half of them should end in something a stranger can reply to without effort.
- Never summarize an essay. A note is its own thing.

Give me {args.n or 8} distinct notes. Vary the structure: contrarian, confession,
micro-story, open question, and one short quotable reframe. Number them.""")
    return 0


def cmd_add(args):
    q = _queue()
    if args.hook and args.hook not in {h["key"] for h in HOOKS}:
        store.err(f"unknown hook '{args.hook}' — run: ./substack.py notes hooks")
        return 1
    item = {
        "id": store.next_id(q["items"]),
        "text": args.text.strip(),
        "kind": args.kind,
        "hook": args.hook or "",
        "target": args.target or "",
        "created": store.today(),
        "status": "queued",
    }
    q["items"].append(item)
    _save(q)
    ok(f"queued #{item['id']} ({item['kind']})")
    if not args.hook and args.kind == "original":
        print(dim("      tag the formula with --hook so `notes best` can rank them later"))
    return 0


def cmd_score(args):
    """Record how a posted note actually performed."""
    q = _queue()
    item = store.find(q["items"], args.id)
    if not item:
        store.err(f"no note #{args.id}")
        return 1
    if item["status"] != "posted":
        warn(f"#{item['id']} isn't marked posted yet — scoring it anyway")
    score = item.get("score", {})
    for field in ("likes", "restacks", "replies", "subs"):
        val = getattr(args, field)
        if val is not None:
            score[field] = val
    score["at"] = store.today()
    item["score"] = score
    _save(q)
    ok(f"scored #{item['id']}: " + ", ".join(f"{k}={v}" for k, v in score.items() if k != "at"))
    if not item.get("hook"):
        print(dim(f"      no hook tagged — set one:  ./substack.py notes tag {item['id']} <hook>"))
    return 0


def cmd_tag(args):
    q = _queue()
    item = store.find(q["items"], args.id)
    if not item:
        store.err(f"no note #{args.id}")
        return 1
    if args.hook not in {h["key"] for h in HOOKS}:
        store.err(f"unknown hook '{args.hook}' — run: ./substack.py notes hooks")
        return 1
    item["hook"] = args.hook
    _save(q)
    ok(f"#{item['id']} tagged {args.hook}")
    return 0


def _weight(score):
    """A single engagement number. Restacks carry you into new audiences, replies
    are the top-weighted ranking signal, likes are nearly free — weight to match."""
    return (score.get("likes", 0)
            + 2 * score.get("replies", 0)
            + 3 * score.get("restacks", 0))


def cmd_best(args):
    """Rank your hook formulas by measured engagement.

    Ranking uses likes/replies/restacks — the numbers Substack actually shows
    you per note. Subs are displayed but never ranked on: Substack can't tie a
    subscriber to a specific note, so that column is your own guess, not data.
    Publication-level subscriber growth belongs in `stats log` and `review`.
    """
    q = _queue()
    scored = [i for i in q["items"] if i.get("score")]
    header("What's working")
    if not scored:
        warn("nothing scored yet")
        bullet("Post a note, mark it done, then score it in a weekly pass:  "
               "./substack.py notes session")
        return 0

    groups = {}
    for i in scored:
        groups.setdefault(i.get("hook") or "untagged", []).append(i)

    rows = []
    for hook, items in groups.items():
        n = len(items)
        subs = sum(i["score"].get("subs", 0) for i in items)
        eng = sum(_weight(i["score"]) for i in items)
        rows.append((eng / n, n, hook, subs))
    rows.sort(reverse=True)

    print(f"  {dim('formula'.ljust(13))}{dim('notes'.rjust(6))}"
          f"{dim('engage/note'.rjust(13))}{dim('subs*'.rjust(8))}")
    for avg_eng, n, hook, subs in rows:
        thin = dim(" ·") if n < 3 else "  "
        print(f"  {bold(hook.ljust(13))}{str(n).rjust(6)}"
              f"{avg_eng:>13.1f}{str(subs).rjust(8)}{thin}")

    print()
    print(dim("  engagement = likes + 2×replies + 3×restacks — what Substack shows per note"))
    print(dim("  * subs are self-attributed guesses; Substack can't tie a subscriber to a"))
    print(dim("    note. A hint, never a ranking. Real growth lives in `review`."))
    if any(n < 3 for _, n, _, _ in rows):
        print(dim("  · fewer than 3 notes — too thin to trust yet"))
    top = rows[0]
    if top[1] >= 3:
        bullet(f"{bold(top[2])} is your strongest formula at {top[0]:.1f} engagement/note. "
               "Use it more, and look at what those notes had in common beyond the shape.")

    print()
    print(f"  {bold('Top individual notes')}")
    for i in sorted(scored, key=lambda i: _weight(i["score"]), reverse=True)[:5]:
        s = i["score"]
        tag = dim(f"[{i.get('hook') or 'untagged'}]")
        subs_note = dim(f"  +{s['subs']} subs*") if s.get("subs") else ""
        print(f"    {green(str(_weight(s)).rjust(5))} {tag} "
              f"{i['text'].split(chr(10))[0][:46]}{subs_note}")
    return 0


def unscored(q):
    """Posted notes with no score yet — the weekly session's worklist."""
    return [i for i in q["items"] if i["status"] == "posted" and not i.get("score")]


def cmd_session(args):
    """Interactive scoring pass — walk every posted-but-unscored note once.

    Scoring one note a day after posting never survives contact with a real
    week; a single batch pass right before `review` does.
    """
    q = _queue()
    pending = unscored(q)
    header(f"Scoring session — {len(pending)} unscored note(s)")
    if not pending:
        ok("every posted note has numbers. Run:  ./substack.py review")
        return 0
    print(dim("  Open each note on Substack and type its numbers:"))
    print(dim("      likes restacks replies [subs]     e.g.  40 4 8  or  40 4 8 2"))
    print(dim("  Enter skips · q stops (progress is saved as you go)"))
    print()

    done = 0
    for item in pending:
        tag = dim(f"[{item.get('hook') or item['kind']}]")
        print(f"  {bold('#' + str(item['id']))} {tag} {item['text'].split(chr(10))[0][:58]}")
        print(f"      {dim('posted ' + item.get('posted', '?'))}")
        try:
            raw = input("      > ").strip()
        except EOFError:
            print()
            break
        if raw.lower() in ("q", "quit"):
            break
        if not raw:
            continue
        try:
            nums = [int(p) for p in raw.split()[:4]]
        except ValueError:
            warn("numbers only — skipped")
            continue
        score = dict(zip(("likes", "restacks", "replies", "subs"), nums))
        score["at"] = store.today()
        item["score"] = score
        _save(q)
        done += 1

    print()
    ok(f"scored {done} of {len(pending)}")
    if done:
        bullet("See what it changed:  ./substack.py notes best")
    return 0


def cmd_queue(args):
    q = _queue()
    items = [i for i in q["items"] if i["status"] == "queued"]
    if not items:
        header("Queue")
        warn("empty — add one:  ./substack.py notes add \"your note\"")
        return 0
    header(f"Queue ({len(items)})")
    for i in items:
        tag = {"original": green, "reply": yellow, "restack": magenta}[i["kind"]](i["kind"])
        first = i["text"].split("\n")[0]
        print(f"  {bold('#' + str(i['id']))} [{tag}] {first[:70]}")
        if i["target"]:
            print(f"       {dim('→ ' + i['target'])}")
    return 0


def cmd_done(args):
    q = _queue()
    item = store.find(q["items"], args.id)
    if not item:
        store.err(f"no queued note #{args.id}")
        return 1
    item["status"] = "posted"
    item["posted"] = store.today()
    q["log"].append({"id": item["id"], "kind": item["kind"], "date": store.today()})
    _save(q)
    ok(f"marked #{item['id']} posted")
    return 0


def cmd_today(args):
    """The daily slate — what the algorithm actually rewards, in ratio."""
    cfg = store.config()
    q = _queue()
    done_today = [l for l in q["log"] if l["date"] == store.today()]
    counts = {k: len([l for l in done_today if l["kind"] == k]) for k in KINDS}
    goals = {
        "original": cfg["notes_per_day"],
        "reply": cfg["replies_per_day"],
        "restack": cfg["restacks_per_day"],
    }

    header(f"Today's slate — {store.today()}")
    for k in KINDS:
        have, want = counts[k], goals[k]
        mark = green("✓") if have >= want else dim("○")
        bar = green("█" * have) + dim("░" * max(0, want - have))
        print(f"  {mark} {k.ljust(9)} {bar}  {have}/{want}")

    print()
    if counts["reply"] < goals["reply"]:
        bullet(bold("Replies are the highest-weighted signal."))
        print(store.wrap("Find notes from writers one tier above you and leave a reply that adds "
                         "a fact, a counter-example, or a story. Never 'great post'.",
                         indent="      "))
    if counts["restack"] < goals["restack"]:
        bullet(bold("Restack with commentary."))
        print(store.wrap("A bare restack teaches the algorithm nothing. Your line on top is what "
                         "tells it you two share an audience.", indent="      "))
    if counts["original"] < goals["original"]:
        pending = [i for i in q["items"] if i["status"] == "queued" and i["kind"] == "original"]
        if pending:
            bullet(f"You have {len(pending)} original(s) queued — post #{pending[0]['id']}.")
        else:
            bullet("Nothing queued. Run:  ./substack.py notes draft \"a thought you had today\"")

    streak = _streak(q["log"])
    print()
    kv("streak", f"{streak} day(s)" if streak else dim("none — start today"))
    return 0


def _streak(log):
    days = {l["date"] for l in log}
    n, d = 0, date.today()
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def cmd_log(args):
    q = _queue()
    log = q["log"][-args.n :] if args.n else q["log"]
    if not log:
        header("Activity log")
        warn("nothing logged yet")
        return 0
    header(f"Activity log (last {len(log)})")
    by_day = {}
    for l in log:
        by_day.setdefault(l["date"], []).append(l["kind"])
    for day in sorted(by_day, reverse=True):
        kinds = by_day[day]
        summary = ", ".join(f"{kinds.count(k)} {k}" for k in KINDS if kinds.count(k))
        kv(day, summary, width=12)
    print()
    kv("streak", f"{_streak(q['log'])} day(s)", width=12)
    return 0


def register(sub):
    p = sub.add_parser("notes", help="Notes engine: hooks, queue, daily slate")
    s = p.add_subparsers(dest="notes_cmd", required=True)

    s.add_parser("hooks", help="list hook formulas").set_defaults(func=cmd_hooks)

    d = s.add_parser("draft", help="render a raw idea through hook formulas")
    d.add_argument("idea")
    d.add_argument("--topic", help="short subject noun, e.g. 'writing'")
    d.add_argument("--hook", help="only this hook key")
    d.add_argument("-n", type=int, help="limit number of drafts")
    d.set_defaults(func=cmd_draft)

    pr = s.add_parser("prompt", help="emit an LLM brief for generating notes in your voice")
    pr.add_argument("idea", nargs="?")
    pr.add_argument("-n", type=int, default=8)
    pr.set_defaults(func=cmd_prompt)

    a = s.add_parser("add", help="queue a note")
    a.add_argument("text")
    a.add_argument("--kind", choices=KINDS, default="original")
    a.add_argument("--hook", help="which formula this uses (see: notes hooks)")
    a.add_argument("--target", help="whose note/post this replies to or restacks")
    a.set_defaults(func=cmd_add)

    sc = s.add_parser("score", help="record how a posted note performed")
    sc.add_argument("id")
    sc.add_argument("--likes", type=int)
    sc.add_argument("--restacks", type=int)
    sc.add_argument("--replies", type=int)
    sc.add_argument("--subs", type=int,
                    help="subscribers you'd guess it earned (a hint — never ranked on)")
    sc.set_defaults(func=cmd_score)

    tg = s.add_parser("tag", help="set the hook formula on an existing note")
    tg.add_argument("id")
    tg.add_argument("hook")
    tg.set_defaults(func=cmd_tag)

    s.add_parser("best", help="rank your hook formulas by measured engagement") \
        .set_defaults(func=cmd_best)

    s.add_parser("session", help="interactive scoring pass over unscored posted notes") \
        .set_defaults(func=cmd_session)

    s.add_parser("queue", help="show the queue").set_defaults(func=cmd_queue)
    s.add_parser("today", help="today's engagement slate").set_defaults(func=cmd_today)

    dn = s.add_parser("done", help="mark a queued note as posted")
    dn.add_argument("id")
    dn.set_defaults(func=cmd_done)

    lg = s.add_parser("log", help="activity history and streak")
    lg.add_argument("-n", type=int, default=14)
    lg.set_defaults(func=cmd_log)
