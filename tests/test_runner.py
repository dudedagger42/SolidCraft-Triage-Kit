"""Offline runner tests: python -m unittest discover -s tests -p test_runner.py."""
import contextlib
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kit"))
import runner as r


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / "usage.json"

    def ledger(self, daily="5", total="100", day="2026-11-19"):
        return r.Ledger(self.path, daily, total, day)

    def charge(self, ledger, amount):
        row, _ = ledger.reserve("sonnet")
        ledger.settle(row, amount)

    def test_decimal_math_and_reload(self):
        ledger = self.ledger(daily="0.3")
        self.charge(ledger, "0.1")
        self.charge(ledger, "0.2")
        with self.assertRaisesRegex(r.Stop, "cap reached"):
            self.ledger(daily="0.3").remaining()

    def test_total_wins_over_daily_and_survives_new_day(self):
        ledger = self.ledger(total="6")
        self.charge(ledger, "4")
        tomorrow = self.ledger(total="6", day="2026-11-20")
        self.assertEqual(tomorrow.remaining(), Decimal("2"))
        self.charge(tomorrow, "2")
        with self.assertRaises(r.Stop):
            self.ledger(total="6", day="2026-11-21").remaining()

    def test_daily_resets_at_utc_boundary(self):
        self.charge(self.ledger(), "5")
        with self.assertRaises(r.Stop):
            self.ledger().remaining()
        self.assertEqual(self.ledger(day="2026-11-20").remaining(), Decimal("5"))

    def test_crash_reservation_blocks_reload(self):
        row, budget = self.ledger().reserve("haiku")
        self.assertEqual(budget, Decimal("5"))
        self.assertTrue(row["pending"])
        with self.assertRaisesRegex(r.Stop, "Unresolved"):
            self.ledger()

    def test_overshoot_is_recorded_and_stops(self):
        self.charge(self.ledger(), "5.12")
        self.assertEqual(json.loads(self.path.read_text())["runs"][0]["usd"], "5.12")
        with self.assertRaises(r.Stop):
            self.ledger().remaining()

    def test_invalid_costs_and_zero_cap(self):
        for value in ("NaN", "Infinity", "-1", "garbage"):
            with self.subTest(value=value), self.assertRaises(r.Stop):
                r.money(value)
        with self.assertRaises(r.Stop):
            self.ledger(daily="0").remaining()
        self.path.write_text("corrupt")
        with self.assertRaises(ValueError):
            self.ledger()

    def test_bad_report_leaves_reservation_pending(self):
        for reported in (None, "NaN", "-1"):
            with self.subTest(reported=reported):
                self.path.unlink(missing_ok=True)
                ledger = self.ledger()
                fake = subprocess.CompletedProcess([], 0, json.dumps({"total_cost_usd": reported, "result": "ok"}), "")
                with patch.object(r.subprocess, "run", return_value=fake), self.assertRaises((r.Stop, ValueError)):
                    r.Claude("fake-key", ledger).ask("haiku", "prompt")
                with self.assertRaises(r.Stop):
                    self.ledger()

    def test_cli_gets_remaining_budget_and_key_in_env_only(self):
        ledger = self.ledger()
        self.charge(ledger, "4.75")
        fake = subprocess.CompletedProcess([], 0, '{"total_cost_usd":0.1,"result":"ok"}', "")
        with patch.dict(os.environ, {}, clear=False), patch.object(r.subprocess, "run", return_value=fake) as run:
            self.assertEqual(r.Claude("fake-key", ledger).ask("haiku", "hello"), "ok")
            args, kw = run.call_args
            self.assertEqual(args[0][args[0].index("--max-budget-usd") + 1], "0.25")
            self.assertNotIn("fake-key", str(args))
            self.assertEqual(kw["env"]["ANTHROPIC_API_KEY"], "fake-key")
            self.assertNotEqual(os.environ.get("ANTHROPIC_API_KEY"), "fake-key")
        self.assertEqual(self.ledger().remaining(), Decimal("0.15"))

    def test_subscription_limit_no_retry_and_no_api_budget(self):
        fake = subprocess.CompletedProcess([], 1, '{"is_error":true,"result":"You hit your limit"}', "")
        with patch.object(r.subprocess, "run", return_value=fake) as run:
            with self.assertRaisesRegex(r.Stop, "plan limit"):
                r.Claude(None, None).ask("sonnet", "hello")
            self.assertEqual(run.call_count, 1)
            self.assertNotIn("--max-budget-usd", run.call_args.args[0])
            self.assertNotIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])
        self.assertFalse(self.path.exists())
        self.assertFalse(r.limit_message({"usage": {"input_tokens": 429}, "result": "ok"}))

    def test_key_roundtrip_permissions_and_no_echo(self):
        with patch.object(r.sys.stdin, "isatty", return_value=True), patch.object(r.getpass, "getpass", return_value="fake-secret"), contextlib.redirect_stdout(io.StringIO()) as output:
            r.set_key(self.root)
        key = self.root / r.KEY_NAME
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        self.assertEqual(r.read_key(key), "fake-secret")
        self.assertNotIn("fake-secret", output.getvalue())
        self.assertFalse(any(p.name.startswith(".key-") for p in self.root.iterdir()))

    def test_key_rejects_unsafe_mode_symlink_empty_and_directory(self):
        key = self.root / r.KEY_NAME
        key.write_text("secret")
        for mode in (0o644, 0o400, 0o660):
            key.chmod(mode)
            with self.assertRaises(r.Stop):
                r.read_key(key)
        key.chmod(0o600)
        link = self.root / "link"
        link.symlink_to(key)
        with self.assertRaises(r.Stop):
            r.read_key(link)
        for value in ("", "two keys", "x" * 4097):
            key.write_text(value)
            with self.assertRaises(r.Stop):
                r.read_key(key)
        with self.assertRaises(r.Stop):
            r.read_key(self.root)

    def test_key_requires_terminal_and_refuses_link_overwrite(self):
        with patch.object(r.sys.stdin, "isatty", return_value=False), patch.object(r.getpass, "getpass") as prompt:
            with self.assertRaises(r.Stop):
                r.set_key(self.root)
            prompt.assert_not_called()
        target = self.root / "target"
        target.write_text("unchanged")
        (self.root / r.KEY_NAME).symlink_to(target)
        with patch.object(r.sys.stdin, "isatty", return_value=True), patch.object(r.getpass, "getpass", return_value="fake"):
            with self.assertRaises(r.Stop):
                r.set_key(self.root)
        self.assertEqual(target.read_text(), "unchanged")

    def test_key_wrong_owner(self):
        key = self.root / r.KEY_NAME
        key.write_text("fake")
        key.chmod(0o600)
        with patch.object(r.os, "getuid", return_value=key.stat().st_uid + 1), self.assertRaises(r.Stop):
            r.read_key(key)

    def controller(self, dry=True):
        return r.Controller(self.root, r.Claude(None, None), "sonnet", dry)

    def test_only_kit_and_case_files_allowed(self):
        controller = self.controller()
        for args in (["bump", "x"], ["post", "1", "--approve"], ["submit", "1", "--res", "reproduced"],
                     ["submit", "1", "--by", "repro"], ["submit", "1", "--by", "first", "--by", "repro"],
                     ["reply", "1", "--file", "/etc/passwd"]):
            with self.subTest(args=args), self.assertRaises(r.Stop):
                controller.kit(args)
        for path in ("state/config.local.json", "../secret", "kit/triage.py", "state/queue/1.json"):
            with self.subTest(path=path), self.assertRaises(r.Stop):
                controller.path(path, write=True)
        (self.root / "state").symlink_to(self.root)
        with self.assertRaises(r.Stop):
            controller.path("state/cases/1.answers.json", write=True)

    def test_claim_is_not_a_comment_preview(self):
        controller = self.controller()
        fake = subprocess.CompletedProcess([], 0, "DRY RUN #123: claimable; no reaction added\n", "")
        with patch.object(r.subprocess, "run", return_value=fake), contextlib.redirect_stdout(io.StringIO()):
            controller.kit(["claim", "123"])
        self.assertEqual(controller.previews, 0)
        self.assertEqual(controller.env["TRIAGE_DRY_RUN"], "1")

    def test_review_fresh_verify_is_required_and_cannot_be_requested(self):
        controller = self.controller()
        for directory in ("state/cases", "state/queue", "docs"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "docs/verify.md").write_text("Verify all checks")
        for suffix in ("json", "answers.json"):
            (self.root / f"state/cases/123.{suffix}").write_text("{}")
        (self.root / "state/queue/123.json").write_text('{"status":"REVIEW"}')
        fake = subprocess.CompletedProcess([], 0, "DRY RUN #123: the comment above was not posted", "")
        with patch.object(controller.claude, "ask", return_value="VERIFY #123 fix: 1") as verify, patch.object(r.subprocess, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            controller.kit(["post", "123"])
            controller.kit(["post", "123"])
            controller.kit(["post", "123"])
            self.assertEqual(verify.call_count, 2)
            run.assert_not_called()
        controller.verify_failures.clear()
        with patch.object(controller.claude, "ask", return_value="VERIFY #123 ok"), patch.object(r.subprocess, "run", return_value=fake) as run, contextlib.redirect_stdout(io.StringIO()):
            controller.kit(["post", "123"])
            self.assertIn("--approve", run.call_args.args[0])
            self.assertEqual(controller.previews, 1)

    def test_exhausted_cap_never_starts_child(self):
        ledger = self.ledger()
        self.charge(ledger, "5")
        with patch.object(r.subprocess, "run") as run, self.assertRaises(r.Stop):
            r.Claude("fake", ledger).ask("haiku", "hello")
        run.assert_not_called()

    def test_global_lock_excludes_another_runner(self):
        with r.locked(self.root), self.assertRaises(r.Stop):
            with r.locked(self.root):
                self.fail("second runner acquired the lock")

    def test_getpass_fallback_cannot_echo(self):
        with patch.object(r.sys.stdin, "isatty", return_value=True), patch.object(r.getpass, "getpass", side_effect=r.getpass.GetPassWarning), self.assertRaises(r.Stop):
            r.set_key(self.root)
        self.assertFalse((self.root / r.KEY_NAME).exists())

    def test_first_run_forced_dry_until_real_preview_then_live(self):
        home = self.root / "home"
        home.mkdir()
        key = home / r.KEY_NAME
        key.write_text("fake")
        key.chmod(0o600)
        seen = []
        preview = False

        def fake_batch(controller, first_model, steps):
            seen.append(controller.dry)
            controller.previews = int(preview)
            return True

        def fake_run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, "volunteer\n" if cmd[:2] == ["gh", "api"] else "", "")

        with patch.object(r, "ROOT", self.root), patch.object(r, "HOME_STATE", home), patch.object(r.shutil, "which", return_value="fake"), patch.object(r.subprocess, "run", side_effect=fake_run), patch.object(r, "batch", side_effect=fake_batch), contextlib.redirect_stdout(io.StringIO()), patch.dict(os.environ, {"TRIAGE_DRY_RUN": "0"}):
            self.assertEqual(r.main([]), 0)
            marker = self.root / "state/runner-dry-run-volunteer.json"
            self.assertFalse(marker.exists())
            preview = True
            self.assertEqual(r.main([]), 0)
            self.assertTrue(marker.exists())
            self.assertEqual(r.main([]), 0)
            self.assertEqual(r.main(["--dry-run"]), 0)
        self.assertEqual(seen, [True, True, False, True])

    def test_stop_releases_unfinished_claims(self):
        controller = self.controller(dry=False)
        controller.claims.add("123")
        fake = subprocess.CompletedProcess([], 0, "claim removed", "")
        with patch.object(r.subprocess, "run", return_value=fake) as run, contextlib.redirect_stdout(io.StringIO()):
            controller.release_claims()
        self.assertIn("unclaim", run.call_args.args[0])
        self.assertFalse(controller.claims)

    def test_missing_report_never_logs_child_output(self):
        ledger = self.ledger()
        fake = subprocess.CompletedProcess([], 1, "fake-secret", "fake-secret")
        with patch.object(r.subprocess, "run", return_value=fake), self.assertRaises(r.Stop) as error:
            r.Claude("fake-secret", ledger).ask("haiku", "hello")
        self.assertNotIn("fake-secret", str(error.exception))
        with self.assertRaises(r.Stop):
            self.ledger()


if __name__ == "__main__":
    unittest.main()
