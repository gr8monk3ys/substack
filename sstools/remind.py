"""Daily nudge — a scheduled reminder that surfaces today's actions.

The whole strategy depends on showing up daily, and a tool only helps if you
open it. This delivers the day's slate to you instead.

Channels, all optional and used together if configured:
  desktop   osascript (macOS) / notify-send (Linux) — needs a logged-in session
  webhook   Slack or Discord incoming webhook — works headless, reaches a phone
  log       always appended to data/nudges.log

Scheduling:
  macOS     launchd agent  (~/Library/LaunchAgents)
  Linux     crontab entry
  neither   `remind status` tells you, and prints the line to install by hand

Caveat worth knowing: on a cloud dev box (Codespaces, etc.) cron only fires
while the machine is awake. If that's where this lives, use a webhook from a
machine that stays on, or run `remind run` yourself as a habit.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

from . import store
from .network import STALE_DAYS
from .store import bold, bullet, dim, green, header, kv, ok, red, warn, yellow

MARKER = "# substack-toolkit-nudge"
PLIST_LABEL = "com.substack.toolkit.nudge"
PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{PLIST_LABEL}.plist")


# --- the digest -------------------------------------------------------------


PLURALS = {"reply": "replies", "restack": "restacks", "original": "originals"}


def _plural(word, n):
    return word if n == 1 else PLURALS.get(word, word + "s")


def digest():
    """(title, [lines]) — short enough for a notification, useful enough to act on."""
    cfg = store.config()
    q = store.load("notes_queue", {"items": [], "log": []})
    net = store.load("network", {"items": []})["items"]
    metrics = store.load("metrics", {"days": []})["days"]

    today_str = store.today()
    done = [l for l in q["log"] if l["date"] == today_str]
    counts = {k: sum(1 for l in done if l["kind"] == k)
              for k in ("original", "reply", "restack")}
    goals = {"original": cfg["notes_per_day"], "reply": cfg["replies_per_day"],
             "restack": cfg["restacks_per_day"]}

    # Streak, and whether today would break it. Count back from today if you've
    # already posted, otherwise from yesterday — a run ending yesterday is a live
    # streak that today is about to break, which is the whole point of the nudge.
    days = {l["date"] for l in q["log"]}
    posted_today = today_str in days
    streak, d = 0, date.today() if posted_today else date.today() - timedelta(days=1)
    while d.isoformat() in days:
        streak += 1
        d -= timedelta(days=1)

    lines = []
    missing = [(k, goals[k] - counts[k]) for k in ("reply", "restack", "original")
               if counts[k] < goals[k]]
    if missing:
        lines.append(" · ".join(f"{n} {_plural(k, n)}" for k, n in missing))
    else:
        lines.append("slate complete")

    if streak and not posted_today:
        lines.append(f"{streak}-day streak at risk")
    elif streak:
        lines.append(f"{streak}-day streak")

    stale = [i for i in net
             if store.parse_date(i.get("touched"))
             and (date.today() - store.parse_date(i["touched"])).days
             >= STALE_DAYS.get(i["status"], 14)]
    if stale:
        names = ", ".join(i["name"] for i in stale[:2])
        lines.append(f"going cold: {names}" + (f" +{len(stale) - 2}" if len(stale) > 2 else ""))

    if metrics:
        last = store.parse_date(metrics[-1]["date"])
        if last and (date.today() - last).days >= 3:
            lines.append(f"numbers not logged in {(date.today() - last).days}d")

    title = f"{cfg['publication'] or 'Substack'} · {date.today():%a %-d %b}"
    return title, lines


# --- delivery ---------------------------------------------------------------


def _desktop(title, body):
    if sys.platform == "darwin" and shutil.which("osascript"):
        safe = body.replace('"', "'")
        subprocess.run(["osascript", "-e",
                        f'display notification "{safe}" with title "{title}"'],
                       check=False, capture_output=True)
        return "desktop (osascript)"
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", title, body], check=False, capture_output=True)
        return "desktop (notify-send)"
    return None


def _webhook(title, body):
    url = store.config().get("webhook")
    if not url:
        return None
    # "text" is Slack's field, "content" is Discord's — both ignore the other.
    payload = json.dumps({"text": f"*{title}*\n{body}", "content": f"**{title}**\n{body}"})
    req = urllib.request.Request(url, data=payload.encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status >= 300:
                return f"webhook (HTTP {r.status})"
        return "webhook"
    except (urllib.error.URLError, OSError) as e:
        return f"webhook FAILED ({e})"


def _log(title, body):
    path = os.path.join(store.DATA, "nudges.log")
    os.makedirs(store.DATA, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{store.now()}  {title} — {'; '.join(body.split(chr(10)))}\n")
    return "log"


def cmd_run(args):
    title, lines = digest()
    body = "\n".join(lines)
    channels = [c for c in (_desktop(title, body), _webhook(title, body), _log(title, body)) if c]

    if not args.quiet:
        header(title)
        for l in lines:
            bullet(l)
        print()
        kv("delivered via", ", ".join(channels))
        if not any(c.startswith(("desktop", "webhook")) for c in channels):
            warn("only logged to disk — no desktop notifier and no webhook configured")
            bullet("./substack.py remind webhook <slack-or-discord-url>")
    return 1 if any("FAILED" in c for c in channels) else 0


def cmd_webhook(args):
    if args.url in ("", "none", "off"):
        store.set_config(webhook="")
        ok("webhook cleared")
        return 0
    if not args.url.startswith("https://"):
        store.err("webhook must be an https:// URL")
        return 1
    store.set_config(webhook=args.url)
    ok("webhook saved")
    bullet("Test it:  ./substack.py remind run")
    return 0


# --- scheduling -------------------------------------------------------------


def _cmd_line():
    python = sys.executable or "python3"
    script = os.path.join(store.ROOT, "substack.py")
    return f"cd {store.ROOT} && {python} {script} remind run --quiet"


def _cron_entry(at):
    hh, mm = (at.split(":") + ["0"])[:2]
    return f"{int(mm)} {int(hh)} * * * {_cmd_line()}  {MARKER}"


def _read_crontab():
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    # Exit 1 with "no crontab" is normal for a user who has never had one.
    return r.stdout if r.returncode == 0 else ""


def _write_crontab(text):
    r = subprocess.run(["crontab", "-"], input=text, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or "").strip()


def _plist(at):
    hh, mm = (at.split(":") + ["0"])[:2]
    python = sys.executable or "/usr/bin/python3"
    script = os.path.join(store.ROOT, "substack.py")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string><string>{script}</string>
    <string>remind</string><string>run</string><string>--quiet</string>
  </array>
  <key>WorkingDirectory</key><string>{store.ROOT}</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>{int(hh)}</integer>
        <key>Minute</key><integer>{int(mm)}</integer></dict>
  <key>RunAtLoad</key><false/>
</dict></plist>
"""


def _validate_time(at):
    try:
        hh, mm = (at.split(":") + ["0"])[:2]
        if 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59:
            return True
    except ValueError:
        pass
    store.err(f"--at must be HH:MM (24h), got {at!r}")
    return False


def cmd_install(args):
    if not _validate_time(args.at):
        return 1
    header("Install daily nudge")

    if args.dry_run:
        kv("would schedule", args.at)
        print(f"  {dim(_cron_entry(args.at))}")
        return 0

    if sys.platform == "darwin":
        os.makedirs(os.path.dirname(PLIST), exist_ok=True)
        with open(PLIST, "w", encoding="utf-8") as f:
            f.write(_plist(args.at))
        subprocess.run(["launchctl", "unload", PLIST], check=False, capture_output=True)
        r = subprocess.run(["launchctl", "load", PLIST], capture_output=True, text=True)
        if r.returncode != 0:
            store.err(f"launchctl load failed: {r.stderr.strip()}")
            return 1
        ok(f"launchd agent installed — fires daily at {args.at}")
        kv("plist", PLIST)
        return 0

    if not shutil.which("crontab"):
        store.err("no crontab on this machine, so nothing can be scheduled here")
        print()
        bullet("This is normal on cloud dev boxes — and cron there only fires while "
               "the box is awake anyway.")
        bullet("Install this line on a machine that stays on:")
        print(f"      {dim(_cron_entry(args.at))}")
        bullet("Or configure a webhook and run the nudge from wherever you work:")
        print(f"      {dim('./substack.py remind webhook <url>')}")
        return 1

    existing = [l for l in _read_crontab().splitlines() if MARKER not in l]
    new = "\n".join(existing + [_cron_entry(args.at), ""])
    written, error = _write_crontab(new)
    if not written:
        store.err(f"could not write crontab: {error}")
        return 1
    ok(f"cron entry installed — fires daily at {args.at}")
    if not shutil.which("notify-send") and not store.config().get("webhook"):
        warn("no notifier available — it will only write to data/nudges.log")
        bullet("./substack.py remind webhook <slack-or-discord-url>")
    return 0


def cmd_uninstall(args):
    header("Remove daily nudge")
    if sys.platform == "darwin":
        if not os.path.exists(PLIST):
            warn("no launchd agent installed")
            return 0
        subprocess.run(["launchctl", "unload", PLIST], check=False, capture_output=True)
        os.remove(PLIST)
        ok("launchd agent removed")
        return 0
    if not shutil.which("crontab"):
        warn("no crontab on this machine — nothing to remove")
        return 0
    lines = _read_crontab().splitlines()
    kept = [l for l in lines if MARKER not in l]
    if len(kept) == len(lines):
        warn("no nudge entry found in your crontab")
        return 0
    written, error = _write_crontab("\n".join(kept + [""]))
    if not written:
        store.err(f"could not write crontab: {error}")
        return 1
    ok("cron entry removed")
    return 0


def cmd_status(args):
    cfg = store.config()
    header("Nudge status")

    if sys.platform == "darwin":
        installed = os.path.exists(PLIST)
        kv("scheduler", "launchd")
        kv("installed", green("yes") if installed else yellow("no"))
    elif shutil.which("crontab"):
        entry = next((l for l in _read_crontab().splitlines() if MARKER in l), None)
        kv("scheduler", "cron")
        kv("installed", green("yes") if entry else yellow("no"))
        if entry:
            print(f"      {dim(entry)}")
    else:
        kv("scheduler", red("none available"))
        print(store.wrap("No crontab on this machine. On a cloud dev box that's expected — "
                         "and cron there would only fire while the box is awake. Use a webhook "
                         "from a machine that stays on, or just run `remind run` as a habit.",
                         indent="      "))

    print()
    desktop = ("osascript" if sys.platform == "darwin" and shutil.which("osascript")
               else "notify-send" if shutil.which("notify-send") else None)
    kv("desktop", green(desktop) if desktop else dim("unavailable"))
    kv("webhook", green("configured") if cfg.get("webhook") else dim("not set"))
    log = os.path.join(store.DATA, "nudges.log")
    kv("log", log if os.path.exists(log) else dim("nothing sent yet"))

    print()
    title, lines = digest()
    print(f"  {bold('Right now it would say')}")
    print(f"    {title}")
    for l in lines:
        print(f"    {dim('· ' + l)}")
    return 0


def register(sub):
    p = sub.add_parser("remind", help="daily nudge: schedule and deliver today's slate")
    s = p.add_subparsers(dest="remind_cmd", required=True)

    r = s.add_parser("run", help="build and deliver the nudge now")
    r.add_argument("--quiet", action="store_true", help="no stdout (for schedulers)")
    r.set_defaults(func=cmd_run)

    i = s.add_parser("install", help="schedule it daily")
    i.add_argument("--at", default="09:00", help="HH:MM, 24h (default 09:00)")
    i.add_argument("--dry-run", action="store_true", help="print the entry, change nothing")
    i.set_defaults(func=cmd_install)

    s.add_parser("uninstall", help="remove the schedule").set_defaults(func=cmd_uninstall)
    s.add_parser("status", help="what's configured and what it would say") \
        .set_defaults(func=cmd_status)

    w = s.add_parser("webhook", help="set a Slack/Discord webhook (or 'none' to clear)")
    w.add_argument("url")
    w.set_defaults(func=cmd_webhook)
