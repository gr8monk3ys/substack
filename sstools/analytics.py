"""Analytics — daily metric log, Substack CSV export ingestion, HTML dashboard.

Substack has no public API, so there are exactly two honest data sources:

  1. A daily snapshot you record yourself      (`stats log`)  — works from day zero
  2. The official CSV export zip                (`stats import`) — Settings → Exports

Column names in Substack's exports have changed several times, so the importer
matches columns fuzzily and tells you what it actually found rather than
silently mapping the wrong field.
"""

import csv
import html
import io
import os
import zipfile
from collections import Counter
from datetime import date, timedelta

from . import store
from .store import bold, bullet, dim, green, header, kv, ok, warn, yellow

# Fuzzy column matching: canonical name -> substrings that identify it.
POST_COLS = {
    "title": ["title"],
    "subtitle": ["subtitle"],
    "date": ["post_date", "date", "published"],
    "type": ["type"],
    "audience": ["audience"],
    "published": ["is_published"],
    "slug": ["slug"],
    "views": ["view"],
    "opens": ["open"],
    "clicks": ["click"],
    "subs_gained": ["subscriber", "signup", "new_free", "new_paid"],
}
SUB_COLS = {
    "email": ["email"],
    "created": ["created_at", "signup", "subscribe_date", "date"],
    "active": ["active_subscription", "is_paid", "plan"],
    "disabled": ["email_disabled", "unsubscribed", "disabled"],
    "source": ["source", "referrer", "utm"],
}


def _match(fieldnames, spec):
    """Map canonical keys to real column names present in this CSV."""
    found, lowered = {}, {f: f.lower().strip() for f in fieldnames or []}
    for canon, needles in spec.items():
        for real, low in lowered.items():
            if any(n in low for n in needles):
                found[canon] = real
                break
    return found


def _read_csv(text):
    try:
        reader = csv.DictReader(io.StringIO(text))
        return list(reader), reader.fieldnames
    except (csv.Error, UnicodeDecodeError):
        return [], None


def _iter_csvs(path):
    """Yield (name, text) for every CSV in a directory, zip, or single file."""
    if os.path.isfile(path) and path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    yield n, z.read(n).decode("utf-8", "replace")
        return
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            yield os.path.basename(path), f.read()
        return
    for root, _, files in os.walk(path):
        for fn in sorted(files):
            if fn.lower().endswith(".csv"):
                with open(os.path.join(root, fn), encoding="utf-8", errors="replace") as f:
                    yield os.path.relpath(os.path.join(root, fn), path), f.read()


def _num(v):
    try:
        return int(float(str(v).replace(",", "").strip() or 0))
    except (ValueError, TypeError):
        return 0


# --- import -----------------------------------------------------------------


def cmd_import(args):
    path = os.path.abspath(os.path.expanduser(args.path))
    if not os.path.exists(path):
        store.err(f"not found: {path}")
        bullet("Get your export: Substack → Settings → Exports → Create new export")
        bullet(f"Then drop the zip in {dim(store.EXPORTS)} and re-run.")
        return 1

    # Substack splits post metadata (posts.csv) and post performance (a stats
    # export) across separate files, so merge them on title rather than
    # appending — otherwise every post shows up twice, once with no views.
    by_title, subs, seen = {}, [], []
    for name, text in _iter_csvs(path):
        rows, fields = _read_csv(text)
        if not rows:
            continue
        pm, sm = _match(fields, POST_COLS), _match(fields, SUB_COLS)
        # A posts file has titles; a subscriber file has emails.
        if "title" in pm:
            seen.append((name, "posts", len(rows), sorted(pm)))
            for r in rows:
                title = r.get(pm.get("title", ""), "").strip()
                if not title:
                    continue
                rec = by_title.setdefault(title.lower(), {"title": title})
                for field, caster in (("subtitle", str), ("type", str), ("audience", str)):
                    val = r.get(pm.get(field, ""), "").strip()
                    if val and not rec.get(field):
                        rec[field] = val
                d = store.parse_date(r.get(pm.get("date", ""), ""))
                if d and not rec.get("date"):
                    rec["date"] = str(d)
                for field in ("views", "opens", "clicks"):
                    val = _num(r.get(pm.get(field, ""), 0))
                    if val:
                        rec[field] = max(val, rec.get(field, 0))
        elif "email" in sm:
            seen.append((name, "subscribers", len(rows), sorted(sm)))
            for r in rows:
                active = str(r.get(sm.get("active", ""), "")).strip().lower()
                subs.append({
                    "created": str(store.parse_date(r.get(sm.get("created", ""), "")) or ""),
                    "paid": active not in ("", "false", "none", "no", "0", "free"),
                    "disabled": str(r.get(sm.get("disabled", ""), "")).strip().lower()
                    in ("true", "yes", "1"),
                    "source": r.get(sm.get("source", ""), "").strip(),
                })
        else:
            seen.append((name, dim("skipped — no title/email column"), len(rows), []))

    header("Import")
    for name, kind, n, cols in seen:
        kv(name[:34], f"{kind}  {dim(str(n) + ' rows')}", width=36)
        if cols:
            print(f"      {dim('columns matched: ' + ', '.join(cols))}")

    posts = sorted(by_title.values(), key=lambda p: p.get("date") or "", reverse=True)
    for p in posts:
        p.setdefault("date", "")
        for field in ("views", "opens", "clicks"):
            p.setdefault(field, 0)

    if not posts and not subs:
        warn("no recognizable posts or subscriber CSV found in that export")
        return 1

    store.save("imported", {"posts": posts, "subscribers": subs, "at": store.now(),
                            "source": path})
    print()
    ok(f"stored {len(posts)} posts, {len(subs)} subscribers")
    bullet("Next:  ./substack.py stats report")
    return 0


# --- manual daily log -------------------------------------------------------


def cmd_log(args):
    log = store.load("metrics", {"days": []})
    day = args.date or store.today()
    entry = next((d for d in log["days"] if d["date"] == day), None)
    if entry is None:
        entry = {"date": day}
        log["days"].append(entry)
    for field in ("subs", "paid", "views", "notes", "followers"):
        val = getattr(args, field)
        if val is not None:
            entry[field] = val
    if args.note:
        entry["note"] = args.note
    log["days"].sort(key=lambda d: d["date"])
    store.save("metrics", log)
    ok(f"logged {day}: " + ", ".join(f"{k}={v}" for k, v in entry.items() if k != "date"))

    days = log["days"]
    if len(days) >= 2:
        prev, cur = days[-2], days[-1]
        if "subs" in prev and "subs" in cur:
            delta = cur["subs"] - prev["subs"]
            arrow = green(f"+{delta}") if delta >= 0 else store.red(str(delta))
            kv("since last log", f"{arrow} subscribers")
    return 0


def cmd_show(args):
    log = store.load("metrics", {"days": []})["days"]
    imp = store.load("imported", {})
    header("Snapshot")
    if log:
        latest = log[-1]
        kv("as of", latest["date"])
        for k in ("subs", "paid", "followers", "views", "notes"):
            if k in latest:
                kv(k, str(latest[k]))
        window = [d for d in log if store.days_ago(d["date"], 30) and "subs" in d]
        if len(window) >= 2:
            growth = window[-1]["subs"] - window[0]["subs"]
            span = max(1, (store.parse_date(window[-1]["date"])
                           - store.parse_date(window[0]["date"])).days)
            kv("30d growth", f"{green('+' + str(growth))} ({growth / span:.1f}/day)")
    else:
        warn("no manual log yet:  ./substack.py stats log --subs 0")

    posts = imp.get("posts", [])
    if posts:
        print()
        ranked = sorted(posts, key=lambda p: p["views"], reverse=True)[:5]
        print(f"  {bold('Top posts by views')}")
        for p in ranked:
            if p["views"]:
                print(f"    {str(p['views']).rjust(7)}  {p['title'][:56]}")
        if not any(p["views"] for p in ranked):
            warn("imported posts carry no view column — export stats separately from the dashboard")
    return 0


# --- html dashboard ---------------------------------------------------------


def _series(days, key):
    return [(d["date"], d[key]) for d in days if key in d]


def _svg_line(points, width=760, height=200, color="#2f6df6"):
    if len(points) < 2:
        return f'<p class="empty">Not enough data yet — log a few more days.</p>'
    vals = [v for _, v in points]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pad = 28
    step = (width - 2 * pad) / (len(points) - 1)
    coords = [
        (pad + i * step, height - pad - ((v - lo) / span) * (height - 2 * pad))
        for i, (_, v) in enumerate(points)
    ]
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area = f"{pad},{height - pad} {path} {coords[-1][0]:.1f},{height - pad}"
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}"/>' for x, y in coords)
    return f"""<svg viewBox="0 0 {width} {height}" class="chart" role="img">
  <polygon points="{area}" fill="{color}" opacity="0.10"/>
  <polyline points="{path}" fill="none" stroke="{color}" stroke-width="2"
            stroke-linejoin="round" stroke-linecap="round"/>
  {dots}
  <text x="{pad}" y="16" class="lbl">{lo:,}</text>
  <text x="{width - pad}" y="16" class="lbl" text-anchor="end">{hi:,}</text>
</svg>"""


def _bars(rows, width=760):
    if not rows:
        return '<p class="empty">No post data imported yet.</p>'
    hi = max(v for _, v in rows) or 1
    out = ['<div class="bars">']
    for label, val in rows:
        pct = 100 * val / hi
        out.append(
            f'<div class="bar"><span class="bl">{html.escape(str(label)[:52])}</span>'
            f'<span class="bt"><i style="width:{pct:.1f}%"></i></span>'
            f'<span class="bv">{val:,}</span></div>'
        )
    out.append("</div>")
    return "".join(out)


def cmd_report(args):
    cfg = store.config()
    days = store.load("metrics", {"days": []})["days"]
    imp = store.load("imported", {})
    posts = [p for p in imp.get("posts", []) if p.get("title")]
    subs = imp.get("subscribers", [])
    q = store.load("notes_queue", {"log": []})

    subs_series = _series(days, "subs")
    views_series = _series(days, "views")

    # Notes cadence over the last 30 days.
    notes_by_day = Counter(l["date"] for l in q.get("log", []))
    last30 = [(date.today() - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    notes_series = [(d, notes_by_day.get(d, 0)) for d in last30]

    # Subscriber signups per month from the export.
    by_month = Counter(s["created"][:7] for s in subs if s.get("created"))
    month_rows = [(m, n) for m, n in sorted(by_month.items())][-12:]

    latest = days[-1] if days else {}
    paid = sum(1 for s in subs if s.get("paid"))
    cards = [
        ("Subscribers", latest.get("subs", len(subs) or "—")),
        ("Paid", latest.get("paid", paid or "—")),
        ("Followers", latest.get("followers", "—")),
        ("Posts", len(posts) or "—"),
        ("Notes (30d)", sum(n for _, n in notes_series) or "—"),
        ("Streak", _streak_len(q.get("log", []))),
    ]
    card_html = "".join(
        f'<div class="card"><span class="cl">{html.escape(l)}</span>'
        f'<span class="cv">{html.escape(str(v))}</span></div>'
        for l, v in cards
    )

    top_posts = [(p["title"], p["views"]) for p in
                 sorted(posts, key=lambda p: p.get("views", 0), reverse=True)[:10]
                 if p.get("views")]

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(cfg['publication'] or 'Substack')} — growth dashboard</title>
<style>
:root {{ --bg:#fff; --fg:#16181d; --mut:#6b7280; --line:#e6e8ec; --accent:#2f6df6; --card:#f7f8fa; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#0f1115; --fg:#e8eaed; --mut:#9aa1ad; --line:#242832; --accent:#6ea0ff; --card:#171a21; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:2.5rem 1.25rem 4rem; background:var(--bg); color:var(--fg);
  font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; }}
main {{ max-width:840px; margin:0 auto; }}
h1 {{ font-size:1.6rem; margin:0 0 .25rem; letter-spacing:-.02em; }}
.sub {{ color:var(--mut); margin:0 0 2rem; font-size:.9rem; }}
h2 {{ font-size:1rem; text-transform:uppercase; letter-spacing:.08em; color:var(--mut);
  margin:2.5rem 0 .75rem; font-weight:600; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:.75rem; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:.85rem 1rem;
  display:flex; flex-direction:column; gap:.25rem; }}
.cl {{ font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; color:var(--mut); }}
.cv {{ font-size:1.5rem; font-weight:650; letter-spacing:-.02em; }}
.panel {{ border:1px solid var(--line); border-radius:10px; padding:1rem; overflow-x:auto; }}
.chart {{ width:100%; height:auto; display:block; min-width:520px; }}
.lbl {{ fill:var(--mut); font-size:11px; }}
.empty {{ color:var(--mut); font-style:italic; margin:.5rem 0; }}
.bars {{ display:flex; flex-direction:column; gap:.4rem; min-width:480px; }}
.bar {{ display:grid; grid-template-columns:1fr 2fr auto; gap:.75rem; align-items:center; font-size:.85rem; }}
.bl {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.bt {{ background:var(--card); border-radius:4px; height:9px; overflow:hidden; }}
.bt i {{ display:block; height:100%; background:var(--accent); }}
.bv {{ color:var(--mut); font-variant-numeric:tabular-nums; }}
footer {{ margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line);
  color:var(--mut); font-size:.8rem; }}
</style></head><body><main>
<h1>{html.escape(cfg['publication'] or 'Untitled publication')}</h1>
<p class="sub">{html.escape(cfg['throughline'] or 'No throughline set yet — run ./substack.py pos build')}
 · generated {html.escape(store.now())}</p>

<div class="cards">{card_html}</div>

<h2>Subscribers over time</h2>
<div class="panel">{_svg_line(subs_series)}</div>

<h2>Notes posted (last 30 days)</h2>
<div class="panel">{_svg_line(notes_series, color="#12a150")}</div>

<h2>Traffic logged</h2>
<div class="panel">{_svg_line(views_series, color="#b4690e")}</div>

<h2>Top posts by views</h2>
<div class="panel">{_bars(top_posts)}</div>

<h2>Signups by month (from export)</h2>
<div class="panel">{_bars(month_rows)}</div>

<footer>Built from your own <code>stats log</code> entries and Substack CSV exports.
Substack has no public API — nothing here is scraped.</footer>
</main></body></html>"""

    out = os.path.abspath(args.out or os.path.join(store.DATA, "report.html"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    header("Report")
    ok(f"wrote {out}")
    if not days and not posts:
        warn("it's mostly empty — log a baseline:  ./substack.py stats log --subs 0 --followers 0")
    return 0


def _streak_len(log):
    days = {l["date"] for l in log}
    n, d = 0, date.today()
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def register(sub):
    p = sub.add_parser("stats", help="metrics log, CSV import, HTML dashboard")
    s = p.add_subparsers(dest="stats_cmd", required=True)

    i = s.add_parser("import", help="ingest a Substack export (zip or folder)")
    i.add_argument("path")
    i.set_defaults(func=cmd_import)

    l = s.add_parser("log", help="record today's numbers by hand")
    l.add_argument("--subs", type=int)
    l.add_argument("--paid", type=int)
    l.add_argument("--views", type=int)
    l.add_argument("--followers", type=int)
    l.add_argument("--notes", type=int)
    l.add_argument("--date", help="YYYY-MM-DD (defaults to today)")
    l.add_argument("--note", help="what you changed or tried")
    l.set_defaults(func=cmd_log)

    s.add_parser("show", help="terminal snapshot").set_defaults(func=cmd_show)

    r = s.add_parser("report", help="build the HTML dashboard")
    r.add_argument("--out")
    r.set_defaults(func=cmd_report)
