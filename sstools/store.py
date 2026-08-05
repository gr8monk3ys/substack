"""Shared storage, paths, and terminal formatting for the Substack toolkit."""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DRAFTS = os.path.join(ROOT, "drafts")
EXPORTS = os.path.join(DATA, "exports")
TEMPLATES = os.path.join(ROOT, "templates")

# --- colors -----------------------------------------------------------------

_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code):
    return (lambda s: f"\033[{code}m{s}\033[0m") if _TTY else (lambda s: s)


bold = _c("1")
dim = _c("2")
green = _c("32")
yellow = _c("33")
blue = _c("36")
red = _c("31")
magenta = _c("35")


def header(text):
    print()
    print(bold(text))
    print(dim("─" * max(len(text), 32)))


def bullet(text, marker="•"):
    print(f"  {dim(marker)} {text}")


def kv(key, value, width=18):
    print(f"  {dim(key.ljust(width))} {value}")


def warn(text):
    print(f"  {yellow('!')} {text}")


def ok(text):
    print(f"  {green('✓')} {text}")


def err(text):
    sys.stdout.flush()  # keep stderr in order with buffered stdout when piped
    print(f"  {red('✗')} {text}", file=sys.stderr)


# --- json store -------------------------------------------------------------


def _path(name):
    return os.path.join(DATA, f"{name}.json")


def load(name, default=None):
    """Load data/<name>.json, returning `default` if absent or corrupt."""
    p = _path(name)
    if not os.path.exists(p):
        return {} if default is None else default
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        err(f"could not read {p} — starting from empty")
        return {} if default is None else default


def save(name, payload):
    os.makedirs(DATA, exist_ok=True)
    p = _path(name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)
    return p


def next_id(items):
    """Smallest positive integer id not already used."""
    used = {i.get("id") for i in items}
    n = 1
    while n in used:
        n += 1
    return n


def find(items, ident):
    for i in items:
        if str(i.get("id")) == str(ident):
            return i
    return None


# --- config -----------------------------------------------------------------

DEFAULT_CONFIG = {
    "publication": "",
    "url": "",
    "author": "",
    "stage": "prelaunch",  # prelaunch | cold | traction | established
    "cadence": "weekly",
    "post_day": "Tuesday",
    "notes_per_day": 1,
    "replies_per_day": 5,
    "restacks_per_day": 2,
    "throughline": "",
}


def config():
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load("config", {}))
    return cfg


def set_config(**kwargs):
    cfg = config()
    cfg.update({k: v for k, v in kwargs.items() if v is not None})
    save("config", cfg)
    return cfg


# --- dates ------------------------------------------------------------------


def today():
    return date.today().isoformat()


def now():
    return datetime.now().replace(microsecond=0).isoformat(" ")


def parse_date(s):
    """Best-effort date parse across the formats Substack exports use."""
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%m/%d/%y"):
        try:
            if fmt is None:
                return datetime.fromisoformat(s).date()
            return datetime.strptime(s[: len(fmt) + 6], fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def days_ago(iso, n):
    d = parse_date(iso)
    return d is not None and d >= date.today() - timedelta(days=n)


def slugify(text, maxlen=60):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s[:maxlen].strip("-") or "untitled"


def ensure_dirs():
    for d in (DATA, DRAFTS, EXPORTS, TEMPLATES):
        os.makedirs(d, exist_ok=True)


def wrap(text, width=76, indent="  "):
    """Wrap without importing textwrap's paragraph handling quirks."""
    words, line, out = str(text).split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(indent + line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(indent + line)
    return "\n".join(out)
