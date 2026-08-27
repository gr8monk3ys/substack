#!/usr/bin/env python3
"""Substack growth toolkit — one CLI for positioning, Notes, drafts, network, and stats.

    ./substack.py plan            what to do today
    ./substack.py --help          everything else

No dependencies, no scraping, no API keys. Substack has no public API; every
number here comes from your own CSV exports or what you log by hand.
"""

import argparse
import sys

from sstools import analytics, network, pipeline, plan, positioning, remind, review, store
from sstools import notes as notes_mod


def build_parser():
    p = argparse.ArgumentParser(
        prog="./substack.py",
        description="Substack growth toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  ./substack.py init --publication "Write Conscious" --author "Ian" --stage prelaunch
  ./substack.py pos worksheet            # find your throughline
  ./substack.py plan                     # today's actions
  ./substack.py notes draft "an idea"    # render it through 10 hook formulas
  ./substack.py notes today              # the daily engagement slate
  ./substack.py notes session            # weekly scoring pass over posted notes
  ./substack.py notes best               # which formulas actually earn engagement
  ./substack.py review                   # weekly: did any of it work?
  ./substack.py remind install --at 08:30   # daily nudge
  ./substack.py remind status
  ./substack.py post new "Working title"
  ./substack.py post repurpose my-draft --queue
  ./substack.py net targets
  ./substack.py stats log --subs 42
  ./substack.py stats report && open data/report.html
""",
    )
    sub = p.add_subparsers(dest="command", required=True)
    for mod in (plan, review, positioning, notes_mod, pipeline, network, analytics, remind):
        mod.register(sub)
    return p


def main(argv=None):
    store.ensure_dirs()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
