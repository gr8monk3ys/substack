"""Network CRM — recommendation partners, cross-promo targets, outreach follow-ups.

Recommendations and restack relationships are the compounding growth lever on
Substack: a recommendation from a publication your size sends readers forever,
where a viral note sends them once. This tracks the relationship, not the metric.

Statuses move in one direction:
    target → engaged → contacted → talking → partnered  (or → cold)
"""

from datetime import timedelta

from . import store
from .store import blue, bold, bullet, dim, green, header, kv, magenta, ok, red, warn, yellow

STATUSES = ["target", "engaged", "contacted", "talking", "partnered", "cold"]
COLORS = {"target": dim, "engaged": yellow, "contacted": blue,
          "talking": magenta, "partnered": green, "cold": red}

# How long to let a status sit before it needs a nudge.
STALE_DAYS = {"target": 7, "engaged": 14, "contacted": 10, "talking": 5,
              "partnered": 60, "cold": 999}

TEMPLATES = {
    "engage": """Before you message anyone, spend two weeks in their comments.

The only opening line that works is one where they already know your name.
Reply substantively to 3-5 of their notes or posts. Not "great piece" —
add a fact, a counter-example, or the thing they left out. Restack one with
your own take on top.

Then, and only then, send the note below.""",

    "recommend": """Hi {name} —

I've been reading {publication} for a while now — {specific} genuinely changed how
I think about {topic}.

I've just added you to my recommendations. No obligation to reciprocate at all;
I recommend things I actually read.

If you ever want a second pair of eyes on a draft, or want to trade notes on
{topic}, I'm around.

— {author}""",

    "guest": """Hi {name} —

{specific} has been sitting in my head since I read it.

I write {publication_mine} — {throughline}. I think there's a piece our two
audiences would both want: {pitch}.

Happy to write it, happy to host you instead, happy to do nothing if the timing's
wrong. Either way, thanks for {publication}.

— {author}""",

    "restack": """No message needed. Restack their post with 1-2 lines of your own
commentary on top — your actual opinion, not a compliment.

This is the highest-ROI outreach on the platform: it puts your name in front of
their readers, and it teaches the algorithm that you two share an audience.
Do it 3 times before you ever ask for anything.""",
}


def _net():
    return store.load("network", {"items": []})


def cmd_add(args):
    data = _net()
    item = {
        "id": store.next_id(data["items"]),
        "name": args.name,
        "publication": args.publication or "",
        "url": args.url or "",
        "topic": args.topic or "",
        "subs": args.subs,
        "status": args.status,
        "created": store.today(),
        "touched": store.today(),
        "history": [],
    }
    data["items"].append(item)
    store.save("network", data)
    ok(f"added #{item['id']} {item['name']} ({item['status']})")
    return 0


def cmd_list(args):
    items = _net()["items"]
    if args.status:
        items = [i for i in items if i["status"] == args.status]
    if not items:
        header("Network")
        warn("empty — add a target:  ./substack.py net add --name \"Ian Cattanach\" "
             "--publication \"Write Conscious\" --topic writing")
        return 0
    order = {s: n for n, s in enumerate(STATUSES)}
    items.sort(key=lambda i: (order.get(i["status"], 9), i["name"].lower()))
    header(f"Network ({len(items)})")
    for i in items:
        c = COLORS.get(i["status"], dim)
        size = f"{i['subs']:,}" if i.get("subs") else "?"
        print(f"  {bold('#' + str(i['id']).ljust(3))} {c(i['status'].ljust(10))} "
              f"{i['name'][:24].ljust(24)} {dim(i['publication'][:26].ljust(26))} {dim(size)}")
    print()
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    print("  " + dim(" · ".join(f"{s}:{n}" for s, n in counts.items() if n)))
    return 0


def cmd_touch(args):
    data = _net()
    item = store.find(data["items"], args.id)
    if not item:
        store.err(f"no contact #{args.id}")
        return 1
    if args.status:
        if args.status not in STATUSES:
            store.err(f"status must be one of: {', '.join(STATUSES)}")
            return 1
        item["status"] = args.status
    item["touched"] = store.today()
    item["history"].append({"date": store.today(), "note": args.note or "",
                            "status": item["status"]})
    store.save("network", data)
    ok(f"#{item['id']} {item['name']} → {item['status']}")
    return 0


def cmd_due(args):
    items = _net()["items"]
    due = []
    for i in items:
        limit = STALE_DAYS.get(i["status"], 14)
        last = store.parse_date(i.get("touched"))
        if last is None:
            continue
        age = (store.parse_date(store.today()) - last).days
        if age >= limit:
            due.append((age, i))
    header("Needs a nudge")
    if not due:
        ok("nobody is stale — good")
        return 0
    due.sort(reverse=True, key=lambda t: t[0])
    for age, i in due:
        c = COLORS.get(i["status"], dim)
        print(f"  {bold('#' + str(i['id']).ljust(3))} {c(i['status'].ljust(10))} "
              f"{i['name'][:26].ljust(26)} {yellow(str(age) + 'd cold')}")
        nxt = {
            "target": "Go engage — reply to 3 of their notes this week.",
            "engaged": "You've built recognition. Send the recommend note.",
            "contacted": "No reply yet. Restack them once more, then let it go.",
            "talking": "Ball is in someone's court. Close the loop today.",
        }.get(i["status"])
        if nxt:
            print(f"       {dim('→ ' + nxt)}")
    return 0


def cmd_template(args):
    cfg = store.config()
    if args.kind not in TEMPLATES:
        store.err(f"kind must be one of: {', '.join(TEMPLATES)}")
        return 1
    item = store.find(_net()["items"], args.id) if args.id else {}
    body = TEMPLATES[args.kind].format(
        name=item.get("name", "{name}"),
        publication=item.get("publication", "{their publication}"),
        topic=item.get("topic", cfg.get("throughline") or "{topic}"),
        specific=args.specific or "{name a specific piece — this is the whole message}",
        author=cfg.get("author") or "{your name}",
        publication_mine=cfg.get("publication") or "{your publication}",
        throughline=cfg.get("throughline") or "{your one-line throughline}",
        pitch=args.pitch or "{the specific piece you'd write}",
    ) if args.kind in ("recommend", "guest") else TEMPLATES[args.kind]

    header(f"Outreach — {args.kind}")
    for line in body.split("\n"):
        print(f"  {line}")
    print()
    if "{" in body:
        warn("fill the {placeholders} — a template that reads like a template gets ignored")
    return 0


def cmd_targets(args):
    header("Where to find partners")
    for where, how in [
        ("Substack Leaderboards", "substack.com/leaderboard — filter by category. Target the "
         "#20-80 range, not the top 10; they still reply."),
        ("Your own feed", "Whoever the Notes algorithm keeps showing you already shares your "
         "audience. That's the algorithm doing the research for you."),
        ("Recommendations of writers you like", "Every publication lists who it recommends. "
         "Those are pre-qualified — they already say yes to recommending."),
        ("Comment sections", "The most interesting commenter on a big publication is usually a "
         "writer with a small one. Best possible peer."),
        ("Restack chains", "See who restacks the writers you admire. Restackers are the single "
         "most valuable relationship type on the platform."),
    ]:
        print(f"  {bold(where)}")
        print(store.wrap(dim(how), indent="      "))
        print()
    print(f"  {bold('The size rule')}")
    print(store.wrap(dim("Aim at publications 1x-3x your size. Below that they can't move your "
                         "numbers; far above that you're invisible until you're not. As you grow, "
                         "re-aim — the ladder moves with you."), indent="      "))
    return 0


def register(sub):
    p = sub.add_parser("net", help="recommendation & cross-promo CRM")
    s = p.add_subparsers(dest="net_cmd", required=True)

    a = s.add_parser("add")
    a.add_argument("--name", required=True)
    a.add_argument("--publication")
    a.add_argument("--url")
    a.add_argument("--topic")
    a.add_argument("--subs", type=int, help="their subscriber count if known")
    a.add_argument("--status", choices=STATUSES, default="target")
    a.set_defaults(func=cmd_add)

    l = s.add_parser("list")
    l.add_argument("--status", choices=STATUSES)
    l.set_defaults(func=cmd_list)

    t = s.add_parser("touch", help="log an interaction / move status")
    t.add_argument("id")
    t.add_argument("--note")
    t.add_argument("--status", choices=STATUSES)
    t.set_defaults(func=cmd_touch)

    s.add_parser("due", help="who has gone stale").set_defaults(func=cmd_due)

    tm = s.add_parser("template", help="outreach message")
    tm.add_argument("kind", choices=list(TEMPLATES))
    tm.add_argument("--id", help="contact id to fill in")
    tm.add_argument("--specific", help="the specific piece of theirs you're referencing")
    tm.add_argument("--pitch", help="for guest: what you'd write")
    tm.set_defaults(func=cmd_template)

    s.add_parser("targets", help="where to find partners").set_defaults(func=cmd_targets)
