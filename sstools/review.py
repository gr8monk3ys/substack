"""Weekly review — did any of it work?

Everything else in this toolkit is input-side: what to post, what you posted,
how many subscribers you have. This is the only command that connects them.
Run it on the same day every week, right after you publish.
"""

import os
import re
from datetime import date, timedelta

from . import store
from .notes import _weight, unscored
from .store import bold, bullet, dim, green, header, kv, magenta, ok, red, warn, yellow


def _window(days_back, span):
    """(start, end) dates for a window ending `days_back` days ago."""
    end = date.today() - timedelta(days=days_back)
    return end - timedelta(days=span - 1), end


def _subs_at(entries, when):
    """Last recorded subscriber count on or before `when`."""
    best = None
    for e in entries:
        d = store.parse_date(e.get("date"))
        if d is not None and d <= when and "subs" in e:
            if best is None or d > store.parse_date(best["date"]):
                best = e
    return best.get("subs") if best else None


def _in(d, start, end):
    parsed = store.parse_date(d)
    return parsed is not None and start <= parsed <= end


def _delta(cur, prev, unit=""):
    if prev is None or cur is None:
        return dim("—")
    diff = cur - prev
    if diff > 0:
        return green(f"+{diff}{unit}")
    if diff < 0:
        return red(f"{diff}{unit}")
    return dim(f"±0{unit}")


def _published_posts(start, end):
    """Drafts marked published in the window, plus anything imported from Substack."""
    out = []
    store.ensure_dirs()
    for fn in sorted(os.listdir(store.DRAFTS)):
        if not fn.endswith(".md"):
            continue
        path = os.path.join(store.DRAFTS, fn)
        meta = {}
        with open(path, encoding="utf-8") as f:
            m = re.match(r"^---\n(.*?)\n---\n", f.read(), re.S)
        if m:
            for line in m.group(1).split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
        if meta.get("status") == "published" and _in(meta.get("date"), start, end):
            out.append(meta.get("title") or fn)
    for p in store.load("imported", {}).get("posts", []):
        if _in(p.get("date"), start, end):
            out.append(p.get("title", "(untitled)"))
    return out


def cmd_review(args):
    span = args.days
    cur_start, cur_end = _window(0, span)
    prev_start, prev_end = _window(span, span)

    metrics = store.load("metrics", {"days": []})["days"]
    q = store.load("notes_queue", {"items": [], "log": []})
    net = store.load("network", {"items": []})["items"]

    header(f"Review — {cur_start} to {cur_end}")

    # --- subscribers --------------------------------------------------------
    now_subs = _subs_at(metrics, cur_end)
    mid_subs = _subs_at(metrics, cur_start - timedelta(days=1))
    old_subs = _subs_at(metrics, prev_start - timedelta(days=1))
    gained = None if (now_subs is None or mid_subs is None) else now_subs - mid_subs
    prev_gained = None if (mid_subs is None or old_subs is None) else mid_subs - old_subs

    print(f"  {bold('Subscribers')}")
    if now_subs is None:
        warn("no subscriber numbers logged — ./substack.py stats log --subs N")
    else:
        kv("total", str(now_subs))
        kv(f"gained ({span}d)", f"{gained if gained is not None else '—'}  "
                                f"{dim('vs')} {prev_gained if prev_gained is not None else '—'} "
                                f"{dim('prior')}  {_delta(gained, prev_gained)}")

    # --- notes activity -----------------------------------------------------
    def counts(start, end):
        c = {}
        for l in q["log"]:
            if _in(l["date"], start, end):
                c[l["kind"]] = c.get(l["kind"], 0) + 1
        return c

    cur_c, prev_c = counts(cur_start, cur_end), counts(prev_start, prev_end)
    print()
    print(f"  {bold('Notes activity')}")
    for kind in ("original", "reply", "restack"):
        a, b = cur_c.get(kind, 0), prev_c.get(kind, 0)
        kv(kind, f"{str(a).rjust(3)}  {dim('vs')} {str(b).rjust(3)} {dim('prior')}  {_delta(a, b)}")

    active_days = len({l["date"] for l in q["log"] if _in(l["date"], cur_start, cur_end)})
    kv("active days", f"{active_days}/{span}")

    # --- what landed --------------------------------------------------------
    scored = [i for i in q["items"]
              if i.get("score") and _in(i["score"].get("at"), cur_start, cur_end)]
    print()
    print(f"  {bold('What landed')}")
    if not scored:
        print(dim("      nothing scored this week"))
    else:
        for i in sorted(scored, key=lambda i: _weight(i["score"]), reverse=True)[:5]:
            s = i["score"]
            print(f"    {green(str(_weight(s)).rjust(5))} "
                  f"{dim('[' + (i.get('hook') or 'untagged') + ']')} "
                  f"{i['text'].split(chr(10))[0][:44]}")
    pending = unscored(q)
    if pending:
        bullet(f"{len(pending)} posted note(s) unscored — score them now, in one pass:  "
               "./substack.py notes session")

    posts = _published_posts(cur_start, cur_end)
    print()
    print(f"  {bold('Published')}")
    if posts:
        for t in posts:
            bullet(t[:64])
    else:
        print(dim(f"      nothing published in the last {span} days"))

    # --- network ------------------------------------------------------------
    moves = [(i, h) for i in net for h in i.get("history", [])
             if _in(h.get("date"), cur_start, cur_end)]
    print()
    print(f"  {bold('Network')}")
    if moves:
        for i, h in moves[-6:]:
            note = f" — {h['note']}" if h.get("note") else ""
            print(f"    {magenta(h['status'].ljust(10))} {i['name'][:22].ljust(22)}"
                  f"{dim(note[:30])}")
    else:
        print(dim("      no contact logged this week"))
    partners = sum(1 for i in net if i["status"] == "partnered")
    kv("partnered", str(partners))

    # --- verdict ------------------------------------------------------------
    print()
    print(f"  {bold('Read of the week')}")
    said = False
    if active_days < span * 0.7:
        bullet(f"You showed up {active_days} of {span} days. Consistency is the variable that "
               "moves distribution most — the algorithm rewards daily presence over bursts.")
        said = True
    if cur_c.get("reply", 0) < cur_c.get("original", 0):
        bullet("You posted more than you replied. Replies are the higher-weighted signal and the "
               "faster path into other people's audiences — invert that ratio.")
        said = True
    if gained is not None and prev_gained is not None and gained < prev_gained:
        bullet(f"Growth slowed ({prev_gained} → {gained}). Before changing your writing, check "
               "whether your reply and restack volume dropped — it usually did.")
        said = True
    if partners == 0 and len(net) > 0:
        bullet("No recommendation partners yet. That's the lever that compounds; a good week of "
               "notes doesn't. Run: ./substack.py net due")
        said = True
    if not posts:
        bullet(f"Nothing published in {span} days. Cadence on a fixed day beats volume — "
               "protect the slot.")
        said = True
    if not said:
        ok("Ratios look right and you shipped. Keep the shape, raise the quality.")

    print()
    print(f"  {bold('Answer these before next week')}")
    for question in (
        "Which note started the most real conversation, and what was actually different about it?",
        "Which conversation this week could become a recommendation in a month?",
        "What did you publish out of obligation rather than interest? Cut that next week.",
    ):
        print(store.wrap(dim("· " + question), indent="    "))
    return 0


def register(sub):
    p = sub.add_parser("review", help="weekly review: did any of it work?")
    p.add_argument("--days", type=int, default=7, help="window length (default 7)")
    p.set_defaults(func=cmd_review)
