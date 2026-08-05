"""Daily plan and stage-aware launch checklist."""

import os
from datetime import date, timedelta

from . import store
from .store import bold, bullet, dim, green, header, kv, magenta, ok, warn, yellow

STAGES = {
    "prelaunch": "Not launched",
    "cold": "Under 100 subscribers",
    "traction": "100–1,000 subscribers",
    "established": "1,000+ subscribers",
}

LAUNCH = [
    ("positioning", "Throughline written and stress-tested", "./substack.py pos worksheet"),
    ("name", "Publication name + URL claimed", "Two to four legible words. Not a pun."),
    ("about", "About page published", "./substack.py pos build"),
    ("welcome", "Welcome post written AND pinned", "Highest-traffic page you will ever have."),
    ("welcome_email", "Automated welcome email set", "Highest open rate you will ever get. "
     "Settings → Emails. Point at 2-3 posts."),
    ("sections", "Three named sections created", "Lets you be wide without looking scattered."),
    ("profile", "Substack profile photo + bio", "Your face, not a logo. Personality brands "
     "need a person."),
    ("notes_warm", "14 days of Notes activity BEFORE launch", "Launching to zero followers "
     "wastes your one launch. Build the audience first, then give it somewhere to go."),
    ("stock", "3 posts written before publishing 1", "So week two doesn't kill you."),
    ("recs", "5 recommendations set", "Recommending others is how you get recommended."),
    ("first_send", "First post published + emailed", "Then tell your existing network directly."),
]


def cmd_plan(args):
    cfg = store.config()
    stage = cfg["stage"]
    q = store.load("notes_queue", {"items": [], "log": []})
    ideas = [i for i in store.load("ideas", {"items": []})["items"] if i["status"] == "open"]
    net = store.load("network", {"items": []})["items"]
    metrics = store.load("metrics", {"days": []})["days"]

    header(f"Today — {store.today()}")
    kv("publication", cfg["publication"] or dim("(unnamed)"))
    kv("stage", STAGES.get(stage, stage))
    kv("throughline", cfg["throughline"][:56] if cfg["throughline"] else dim("(not set)"))

    done_today = [l for l in q["log"] if l["date"] == store.today()]
    counts = {k: sum(1 for l in done_today if l["kind"] == k)
              for k in ("original", "reply", "restack")}

    print()
    print(f"  {bold('Do these today')}")

    todo = []
    if stage == "prelaunch":
        pending = [c for c in LAUNCH if not _checked(c[0])]
        if pending:
            key, label, how = pending[0]
            todo.append((f"LAUNCH: {label}", how))
            if len(pending) > 1:
                todo.append((f"Then: {pending[1][1]}", pending[1][2]))

    if counts["reply"] < cfg["replies_per_day"]:
        todo.append((f"{cfg['replies_per_day'] - counts['reply']} substantive replies on other "
                     "people's notes",
                     "Highest-weighted signal in the 2026 algorithm. Add a fact or a "
                     "counter-example — never 'great post'."))
    if counts["restack"] < cfg["restacks_per_day"]:
        todo.append((f"{cfg['restacks_per_day'] - counts['restack']} restacks with commentary",
                     "Teaches the algorithm you share an audience with that writer."))
    if counts["original"] < cfg["notes_per_day"]:
        queued = [i for i in q["items"] if i["status"] == "queued" and i["kind"] == "original"]
        todo.append((f"Post {cfg['notes_per_day'] - counts['original']} original note",
                     f"#{queued[0]['id']} is queued" if queued
                     else "./substack.py notes draft \"a thought you had today\""))
    if len(ideas) < 5:
        todo.append(("Capture ideas — bank is thin",
                     f"{len(ideas)} open. Aim for 10+ so you never write from a blank page."))

    stale = [i for i in net if _stale(i)]
    if stale:
        todo.append((f"{len(stale)} network contact(s) going cold", "./substack.py net due"))
    if len(net) < 10 and stage in ("prelaunch", "cold"):
        todo.append((f"Add network targets ({len(net)}/10)", "./substack.py net targets"))

    if not metrics or metrics[-1]["date"] != store.today():
        todo.append(("Log today's numbers", "./substack.py stats log --subs N --followers N"))

    if not todo:
        ok("everything's done. Go write something.")
    for label, how in todo:
        print(f"  {yellow('□')} {bold(label)}")
        print(f"      {dim(how)}")

    print()
    streak = _streak(q["log"])
    kv("streak", green(f"{streak} days") if streak else yellow("0 — start today"))
    return 0


def _stale(item):
    from .network import STALE_DAYS
    last = store.parse_date(item.get("touched"))
    if last is None:
        return False
    return (date.today() - last).days >= STALE_DAYS.get(item["status"], 14)


def _streak(log):
    days = {l["date"] for l in log}
    n, d = 0, date.today()
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def _checked(key):
    return store.load("checklist", {}).get(key, False)


def cmd_checklist(args):
    state = store.load("checklist", {})
    if args.check:
        keys = [c[0] for c in LAUNCH]
        if args.check not in keys:
            store.err(f"unknown item '{args.check}' — one of: {', '.join(keys)}")
            return 1
        state[args.check] = not state.get(args.check, False)
        store.save("checklist", state)
    header("Launch checklist")
    done = 0
    for key, label, how in LAUNCH:
        is_done = state.get(key, False)
        done += is_done
        mark = green("✓") if is_done else dim("☐")
        name = dim(label) if is_done else bold(label)
        print(f"  {mark} {name}  {dim('[' + key + ']')}")
        if not is_done:
            print(store.wrap(dim(how), indent="      "))
    print()
    kv("progress", f"{done}/{len(LAUNCH)}")
    print(dim("  Toggle:  ./substack.py checklist --check welcome"))
    return 0


def cmd_init(args):
    cfg = store.set_config(
        publication=args.publication,
        url=args.url,
        author=args.author,
        stage=args.stage,
    )
    store.ensure_dirs()
    header("Config")
    for k, v in cfg.items():
        kv(k, str(v) if v != "" else dim("(unset)"))
    print()
    bullet("Next:  ./substack.py pos worksheet")
    return 0


def register(sub):
    sub.add_parser("plan", help="what to do today").set_defaults(func=cmd_plan)

    c = sub.add_parser("checklist", help="launch checklist")
    c.add_argument("--check", help="toggle an item by key")
    c.set_defaults(func=cmd_checklist)

    i = sub.add_parser("init", help="set publication config")
    i.add_argument("--publication")
    i.add_argument("--url")
    i.add_argument("--author")
    i.add_argument("--stage", choices=list(STAGES))
    i.set_defaults(func=cmd_init)
