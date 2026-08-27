"""Test suite for the Substack toolkit.

Covers the parsing and aggregation logic — the parts that silently produce wrong
answers rather than crashing. Every bug found during the original build lives
here as a regression test.

    python3 -m unittest discover tests -v
"""

import argparse
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sstools import analytics, network, notes, pipeline, positioning, remind, review, store


def quiet(fn, *a, **kw):
    """Run a command, swallow stdout and stderr, return (exit_code, stdout)."""
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(io.StringIO()):
        code = fn(*a, **kw)
    return code, buf.getvalue()


class TempStore(unittest.TestCase):
    """Redirects the toolkit's data/drafts dirs at a temp location per test."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._saved = (store.DATA, store.DRAFTS, store.EXPORTS)
        store.DATA = os.path.join(self.tmp, "data")
        store.DRAFTS = os.path.join(self.tmp, "drafts")
        store.EXPORTS = os.path.join(store.DATA, "exports")
        os.makedirs(store.DATA)
        os.makedirs(store.DRAFTS)

    def tearDown(self):
        store.DATA, store.DRAFTS, store.EXPORTS = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


# --- store ------------------------------------------------------------------


class TestStore(TempStore):
    def test_parse_date_formats(self):
        """Substack has shipped several date formats across export versions."""
        cases = {
            "2026-03-11": date(2026, 3, 11),
            "2026-03-11T09:00:00.000Z": date(2026, 3, 11),
            "2026-03-11 09:00:00": date(2026, 3, 11),
            "03/11/2026": date(2026, 3, 11),
            "posted on 2026-03-11 somewhere": date(2026, 3, 11),
        }
        for raw, want in cases.items():
            self.assertEqual(store.parse_date(raw), want, f"failed on {raw!r}")

    def test_parse_date_rejects_junk(self):
        for raw in ("", None, "not a date", "13/45/9999"):
            self.assertIsNone(store.parse_date(raw), f"should reject {raw!r}")

    def test_slugify(self):
        self.assertEqual(store.slugify("The Container Problem!"), "the-container-problem")
        self.assertEqual(store.slugify("  ***  "), "untitled")
        self.assertLessEqual(len(store.slugify("x" * 200)), 60)

    def test_next_id_fills_gaps(self):
        self.assertEqual(store.next_id([]), 1)
        self.assertEqual(store.next_id([{"id": 1}, {"id": 3}]), 2)

    def test_save_load_roundtrip(self):
        store.save("thing", {"a": [1, 2]})
        self.assertEqual(store.load("thing"), {"a": [1, 2]})

    def test_load_survives_corrupt_json(self):
        os.makedirs(store.DATA, exist_ok=True)
        with open(os.path.join(store.DATA, "broken.json"), "w") as f:
            f.write("{not json")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(store.load("broken", {"fallback": True}), {"fallback": True})


# --- analytics --------------------------------------------------------------


class TestColumnMatching(unittest.TestCase):
    def test_matches_renamed_columns(self):
        m = analytics._match(["post_date", "title", "Total Views"], analytics.POST_COLS)
        self.assertEqual(m["date"], "post_date")
        self.assertEqual(m["title"], "title")
        self.assertEqual(m["views"], "Total Views")

    def test_absent_columns_are_omitted(self):
        m = analytics._match(["title"], analytics.POST_COLS)
        self.assertNotIn("views", m)

    def test_num_tolerates_formatting(self):
        self.assertEqual(analytics._num("1,204"), 1204)
        self.assertEqual(analytics._num(""), 0)
        self.assertEqual(analytics._num("n/a"), 0)
        self.assertEqual(analytics._num("88.0"), 88)


class TestImport(TempStore):
    POSTS = ("post_id,post_date,is_published,type,audience,title\n"
             "1,2026-01-14,true,newsletter,everyone,The Container Problem\n"
             "2,2026-02-03,true,newsletter,everyone,You Are Not Distracted\n")
    STATS = ("title,views,opens,clicks\n"
             "The Container Problem,4210,1830,290\n"
             "You Are Not Distracted,9120,3400,610\n")
    EMAILS = ("email,active_subscription,email_disabled,created_at\n"
              "a@x.com,false,false,2026-01-02\n"
              "b@x.com,true,false,2026-01-19\n")

    def _export(self, as_zip=False):
        d = os.path.join(self.tmp, "export")
        os.makedirs(d, exist_ok=True)
        for name, body in (("posts.csv", self.POSTS), ("post_stats.csv", self.STATS),
                           ("email_list.csv", self.EMAILS)):
            with open(os.path.join(d, name), "w") as f:
                f.write(body)
        if not as_zip:
            return d
        z = os.path.join(self.tmp, "export.zip")
        with zipfile.ZipFile(z, "w") as zf:
            for name in os.listdir(d):
                zf.write(os.path.join(d, name), name)
        return z

    def test_merges_metadata_and_stats_on_title(self):
        """Regression: posts.csv and the stats export used to both append,
        yielding 4 records for 2 posts, half of them with zero views."""
        code, _ = quiet(analytics.cmd_import, argparse.Namespace(path=self._export()))
        self.assertEqual(code, 0)
        posts = store.load("imported")["posts"]
        self.assertEqual(len(posts), 2, "posts were double-counted")
        merged = {p["title"]: p for p in posts}
        self.assertEqual(merged["The Container Problem"]["views"], 4210)
        self.assertEqual(merged["The Container Problem"]["type"], "newsletter")
        self.assertEqual(merged["The Container Problem"]["date"], "2026-01-14")

    def test_reads_zip_and_directory_alike(self):
        quiet(analytics.cmd_import, argparse.Namespace(path=self._export(as_zip=True)))
        self.assertEqual(len(store.load("imported")["posts"]), 2)

    def test_classifies_subscribers_and_paid_status(self):
        quiet(analytics.cmd_import, argparse.Namespace(path=self._export()))
        subs = store.load("imported")["subscribers"]
        self.assertEqual(len(subs), 2)
        self.assertEqual(sum(1 for s in subs if s["paid"]), 1)

    def test_missing_path_exits_nonzero(self):
        code, _ = quiet(analytics.cmd_import, argparse.Namespace(path="/nope/missing.zip"))
        self.assertEqual(code, 1)

    def test_report_is_self_contained(self):
        quiet(analytics.cmd_import, argparse.Namespace(path=self._export()))
        out = os.path.join(self.tmp, "report.html")
        quiet(analytics.cmd_report, argparse.Namespace(out=out))
        with open(out) as f:
            html = f.read()
        self.assertIn("<svg", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_svg_handles_thin_data(self):
        """One data point can't make a line — must not divide by zero."""
        self.assertIn("Not enough data", analytics._svg_line([("2026-01-01", 5)]))
        self.assertIn("<svg", analytics._svg_line([("2026-01-01", 5), ("2026-01-02", 5)]))


# --- pipeline ---------------------------------------------------------------


class TestPullQuotes(unittest.TestCase):
    BODY = ("Everyone thinks a personality brand means you can write about anything.\n\n"
            "## The container problem\n\n"
            "A stranger scrolling Notes gives you about two seconds of attention.\n\n"
            "- a bullet point that should not be quoted verbatim with its marker\n")

    def test_headings_are_not_glued_to_sentences(self):
        """Regression: '## The container problem  A stranger scrolling...' """
        for q in pipeline.pull_quotes(self.BODY):
            self.assertNotIn("##", q)
            self.assertFalse(q.startswith("The container problem A"))

    def test_list_markers_stripped(self):
        for q in pipeline.pull_quotes(self.BODY):
            self.assertFalse(q.startswith("- "))

    def test_respects_length_bounds_and_limit(self):
        quotes = pipeline.pull_quotes("Tiny. " + ("A long enough sentence to qualify here. " * 10))
        self.assertLessEqual(len(quotes), 6)
        self.assertTrue(all(40 <= len(q) <= 220 for q in quotes))
        self.assertNotIn("Tiny.", quotes)

    def test_empty_body(self):
        self.assertEqual(pipeline.pull_quotes(""), [])


class TestDrafts(TempStore):
    def test_new_draft_does_not_overwrite(self):
        a = pipeline._new_draft("Same Title")
        b = pipeline._new_draft("Same Title")
        self.assertNotEqual(a, b)
        self.assertTrue(os.path.exists(a) and os.path.exists(b))

    def test_frontmatter_and_body_split(self):
        path = pipeline._new_draft("A Title")
        with open(path, "a") as f:
            f.write("\nReal body text.\n")
        self.assertEqual(pipeline._frontmatter(path)["title"], "A Title")
        body = pipeline._body(path)
        self.assertIn("Real body text.", body)
        self.assertNotIn("<!--", body, "template comments must not count as body")
        self.assertNotIn("---", body)

    def test_resolve_by_partial_name(self):
        pipeline._new_draft("The Container Problem")
        self.assertIsNotNone(pipeline._resolve("container"))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertIsNone(pipeline._resolve("nothing-like-this"))


# --- notes ------------------------------------------------------------------


class TestNotes(TempStore):
    def _post(self, hook, subs, restacks=0, replies=0, likes=0):
        args = argparse.Namespace(text=f"note {hook}", kind="original", hook=hook, target=None)
        quiet(notes.cmd_add, args)
        q = store.load("notes_queue")
        nid = q["items"][-1]["id"]
        quiet(notes.cmd_done, argparse.Namespace(id=nid))
        quiet(notes.cmd_score, argparse.Namespace(
            id=nid, subs=subs, restacks=restacks, replies=replies, likes=likes))
        return nid

    def test_weight_ranks_restacks_above_likes(self):
        self.assertGreater(notes._weight({"restacks": 1}), notes._weight({"likes": 2}))
        self.assertGreater(notes._weight({"replies": 1}), notes._weight({"likes": 1}))

    def test_add_rejects_unknown_hook(self):
        code, _ = quiet(notes.cmd_add, argparse.Namespace(
            text="x", kind="original", hook="bogus", target=None))
        self.assertEqual(code, 1)

    def test_best_ranks_by_engagement_per_note(self):
        self._post("story", 0, restacks=6, replies=8, likes=30)
        self._post("story", 0, restacks=4, replies=5, likes=20)
        self._post("list", 0, restacks=0, replies=0, likes=2)
        _, out = quiet(notes.cmd_best, argparse.Namespace())
        self.assertLess(out.index("story"), out.index("list"), "story should rank above list")

    def test_best_ignores_subs_when_ranking(self):
        """Subs are self-attributed guesses — Substack can't tie a subscriber to
        a note, so a big subs claim must never beat measured engagement."""
        self._post("confession", 50, restacks=0, replies=0, likes=1)
        self._post("story", 0, restacks=5, replies=6, likes=25)
        _, out = quiet(notes.cmd_best, argparse.Namespace())
        self.assertLess(out.index("story"), out.index("confession"),
                        "measured engagement should outrank claimed subs")

    def test_best_flags_thin_samples(self):
        self._post("story", 10)
        _, out = quiet(notes.cmd_best, argparse.Namespace())
        self.assertIn("too thin to trust", out)

    def test_best_with_no_scores(self):
        code, out = quiet(notes.cmd_best, argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertIn("nothing scored yet", out)

    def test_score_unknown_id(self):
        code, _ = quiet(notes.cmd_score, argparse.Namespace(
            id="99", subs=1, restacks=None, replies=None, likes=None))
        self.assertEqual(code, 1)

    def _post_unscored(self, hook="story"):
        quiet(notes.cmd_add, argparse.Namespace(
            text=f"unscored {hook}", kind="original", hook=hook, target=None))
        nid = store.load("notes_queue")["items"][-1]["id"]
        quiet(notes.cmd_done, argparse.Namespace(id=nid))
        return nid

    def test_session_scores_posted_notes(self):
        self._post_unscored()
        self._post_unscored()
        with mock.patch("builtins.input", side_effect=["40 4 8 2", "10 1 0"]):
            code, out = quiet(notes.cmd_session, argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertIn("scored 2 of 2", out)
        items = store.load("notes_queue")["items"]
        self.assertEqual(items[0]["score"]["likes"], 40)
        self.assertEqual(items[0]["score"]["subs"], 2)
        self.assertEqual(items[1]["score"]["replies"], 0)
        self.assertNotIn("subs", items[1]["score"], "unentered fields must stay absent")

    def test_session_skip_and_quit_keep_progress(self):
        self._post_unscored()
        self._post_unscored()
        self._post_unscored()
        with mock.patch("builtins.input", side_effect=["", "5 0 1", "q"]):
            _, out = quiet(notes.cmd_session, argparse.Namespace())
        self.assertIn("scored 1 of 3", out)
        items = store.load("notes_queue")["items"]
        self.assertNotIn("score", items[0], "Enter must skip without scoring")
        self.assertEqual(items[1]["score"]["likes"], 5)

    def test_session_survives_eof_and_junk(self):
        self._post_unscored()
        self._post_unscored()
        with mock.patch("builtins.input", side_effect=["not numbers", EOFError]):
            code, out = quiet(notes.cmd_session, argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertIn("scored 0 of 2", out)

    def test_session_with_nothing_pending(self):
        code, out = quiet(notes.cmd_session, argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertIn("every posted note has numbers", out)

    def test_streak_counts_consecutive_days(self):
        today = date.today()
        log = [{"date": (today - timedelta(days=i)).isoformat()} for i in (0, 1, 2, 5)]
        self.assertEqual(notes._streak(log), 3)
        self.assertEqual(notes._streak([]), 0)


# --- review -----------------------------------------------------------------


class TestReview(TempStore):
    ENTRIES = [{"date": "2026-01-01", "subs": 10}, {"date": "2026-01-08", "subs": 25},
               {"date": "2026-01-15", "subs": 60}]

    def test_subs_at_uses_latest_on_or_before(self):
        self.assertEqual(review._subs_at(self.ENTRIES, date(2026, 1, 10)), 25)
        self.assertEqual(review._subs_at(self.ENTRIES, date(2026, 1, 8)), 25)

    def test_subs_at_before_any_data(self):
        self.assertIsNone(review._subs_at(self.ENTRIES, date(2025, 12, 1)))

    def test_subs_at_ignores_entries_without_subs(self):
        entries = [{"date": "2026-01-01", "subs": 10}, {"date": "2026-01-09", "views": 400}]
        self.assertEqual(review._subs_at(entries, date(2026, 1, 10)), 10)

    def test_window_is_inclusive_and_correct_length(self):
        start, end = review._window(0, 7)
        self.assertEqual(end, date.today())
        self.assertEqual((end - start).days, 6)

    def test_windows_do_not_overlap(self):
        cur_start, _ = review._window(0, 7)
        _, prev_end = review._window(7, 7)
        self.assertLess(prev_end, cur_start)

    def test_runs_on_empty_state(self):
        code, out = quiet(review.cmd_review, argparse.Namespace(days=7))
        self.assertEqual(code, 0)
        self.assertIn("Review", out)

    def test_flags_unscored_posted_notes(self):
        quiet(notes.cmd_add, argparse.Namespace(
            text="posted but never scored", kind="original", hook=None, target=None))
        quiet(notes.cmd_done, argparse.Namespace(id=1))
        _, out = quiet(review.cmd_review, argparse.Namespace(days=7))
        self.assertIn("1 posted note(s) unscored", out)
        self.assertIn("notes session", out)


# --- positioning ------------------------------------------------------------


class TestPositioning(unittest.TestCase):
    def test_sent_capitalizes_and_terminates(self):
        self.assertEqual(positioning._sent("how a person reads"), "How a person reads.")
        self.assertEqual(positioning._sent("Already done."), "Already done.")
        self.assertEqual(positioning._sent("A question?"), "A question?")
        self.assertEqual(positioning._sent(""), "")

    def test_sent_can_skip_the_period(self):
        self.assertEqual(positioning._sent("a subtitle", period=False), "A subtitle")

    def test_worksheet_parses_filled_fields(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("## Who\nname: Lorenzo\nthroughline: how attention survives\nempty:\n")
            path = f.name
        try:
            fields = positioning._parse(path)
            self.assertEqual(fields["name"], "Lorenzo")
            self.assertEqual(fields["throughline"], "how attention survives")
            self.assertEqual(fields["empty"], "")
        finally:
            os.unlink(path)


# --- network ----------------------------------------------------------------


class TestNetwork(TempStore):
    def test_every_status_has_a_staleness_rule_and_color(self):
        for status in network.STATUSES:
            self.assertIn(status, network.STALE_DAYS)
            self.assertIn(status, network.COLORS)

    def test_touch_records_history(self):
        quiet(network.cmd_add, argparse.Namespace(
            name="Ian", publication="WC", url=None, topic="writing", subs=12000, status="target"))
        quiet(network.cmd_touch, argparse.Namespace(id="1", note="replied", status="engaged"))
        item = store.load("network")["items"][0]
        self.assertEqual(item["status"], "engaged")
        self.assertEqual(len(item["history"]), 1)

    def test_due_flags_stale_contacts(self):
        quiet(network.cmd_add, argparse.Namespace(
            name="Old", publication="", url=None, topic="", subs=None, status="target"))
        data = store.load("network")
        data["items"][0]["touched"] = (date.today() - timedelta(days=60)).isoformat()
        store.save("network", data)
        _, out = quiet(network.cmd_due, argparse.Namespace())
        self.assertIn("Old", out)
        self.assertIn("60d cold", out)

    def test_partnered_contacts_are_not_nagged(self):
        quiet(network.cmd_add, argparse.Namespace(
            name="Partner", publication="", url=None, topic="", subs=None, status="partnered"))
        data = store.load("network")
        data["items"][0]["touched"] = (date.today() - timedelta(days=30)).isoformat()
        store.save("network", data)
        _, out = quiet(network.cmd_due, argparse.Namespace())
        self.assertNotIn("Partner", out)


# --- remind -----------------------------------------------------------------


class TestRemind(TempStore):
    def _log_days(self, *offsets):
        today = date.today()
        store.save("notes_queue", {"items": [], "log": [
            {"id": i, "kind": "original", "date": (today - timedelta(days=n)).isoformat()}
            for i, n in enumerate(offsets, 1)]})

    def test_streak_ending_yesterday_is_at_risk(self):
        """Regression: a live streak that today would break must warn, but the
        naive count-back-from-today returns 0 and says nothing."""
        self._log_days(1, 2, 3)
        _, lines = remind.digest()
        self.assertIn("3-day streak at risk", lines)

    def test_streak_including_today_is_not_at_risk(self):
        self._log_days(0, 1, 2)
        _, lines = remind.digest()
        self.assertIn("3-day streak", lines)
        self.assertNotIn("3-day streak at risk", lines)

    def test_broken_streak_is_silent(self):
        self._log_days(4, 5, 6)
        _, lines = remind.digest()
        self.assertFalse(any("streak" in l for l in lines))

    def test_pluralization(self):
        self.assertEqual(remind._plural("reply", 5), "replies")
        self.assertEqual(remind._plural("reply", 1), "reply")
        self.assertEqual(remind._plural("restack", 2), "restacks")

    def test_digest_flags_stale_contact(self):
        store.save("network", {"items": [{
            "id": 1, "name": "Ian", "status": "target",
            "touched": (date.today() - timedelta(days=30)).isoformat(), "history": []}]})
        _, lines = remind.digest()
        self.assertTrue(any("going cold: Ian" in l for l in lines))

    def test_digest_flags_unlogged_numbers(self):
        store.save("metrics", {"days": [
            {"date": (date.today() - timedelta(days=9)).isoformat(), "subs": 40}]})
        _, lines = remind.digest()
        self.assertTrue(any("not logged in 9d" in l for l in lines))

    def test_digest_survives_empty_state(self):
        title, lines = remind.digest()
        self.assertTrue(title)
        self.assertTrue(lines)

    def test_cron_entry_is_wellformed(self):
        entry = remind._cron_entry("08:30")
        fields = entry.split()
        self.assertEqual(fields[:5], ["30", "8", "*", "*", "*"])
        self.assertIn("remind run --quiet", entry)
        self.assertIn(remind.MARKER, entry)

    def test_cron_entry_strips_leading_zeros(self):
        self.assertTrue(remind._cron_entry("09:05").startswith("5 9 "))

    def test_install_rejects_bad_time(self):
        code, _ = quiet(remind.cmd_install,
                        argparse.Namespace(at="99:99", dry_run=True))
        self.assertEqual(code, 1)

    def test_webhook_requires_https(self):
        code, _ = quiet(remind.cmd_webhook, argparse.Namespace(url="http://insecure"))
        self.assertEqual(code, 1)
        self.assertFalse(store.config().get("webhook"))

    def test_webhook_can_be_cleared(self):
        store.set_config(webhook="https://hooks.example.com/x")
        quiet(remind.cmd_webhook, argparse.Namespace(url="none"))
        self.assertEqual(store.config().get("webhook"), "")

    def test_run_always_writes_the_log(self):
        # Stub the desktop channel so running the suite on a machine with
        # notify-send/osascript doesn't fire a real notification.
        original = remind._desktop
        remind._desktop = lambda title, body: None
        try:
            code, _ = quiet(remind.cmd_run, argparse.Namespace(quiet=False))
        finally:
            remind._desktop = original
        self.assertEqual(code, 0)
        with open(os.path.join(store.DATA, "nudges.log")) as f:
            self.assertIn("·", f.read())


if __name__ == "__main__":
    unittest.main()
