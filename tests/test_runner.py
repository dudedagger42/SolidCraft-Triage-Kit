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

    def test_auto_subscription_api_and_reset_across_processes(self):
        now = [r.dt.datetime(2026, 11, 19, 17, tzinfo=r.dt.timezone.utc)]
        state = self.root / "subscription.json"
        limit = subprocess.CompletedProcess([], 1, json.dumps({"is_error": True,
            "result": "You've hit your limit · resets 1pm (America/New_York)"}), "")
        ok = subprocess.CompletedProcess([], 0, '{"total_cost_usd":0.2,"result":"ok"}', "")
        def client():
            return r.Claude("fake-key", None, auth="auto", state_path=state,
                            ledger_factory=self.ledger, clock=lambda: now[0])
        first = client()
        first.issue = 123
        first.start_triage(123, True)
        with patch.object(r.subprocess, "run", side_effect=[ok, limit, ok]) as run:
            first.ask("haiku", "screen")
            self.assertFalse(self.path.exists())
            first.ask("sonnet", "draft")
            self.assertEqual(["ANTHROPIC_API_KEY" in c.kwargs["env"] for c in run.call_args_list], [False, False, True])
            self.assertEqual(run.call_args_list[1].kwargs["input"], run.call_args_list[2].kwargs["input"])
            self.assertIn("--max-budget-usd", run.call_args.args[0])
        self.assertEqual(json.loads(state.read_text())["reset_at"], "2026-11-19T18:00:00+00:00")
        with contextlib.redirect_stdout(io.StringIO()) as output:
            first.tier_summary()
        self.assertIn("Triage #123: api, subscription; API cost: $0.200000", output.getvalue())
        second = client()
        with patch.object(r.subprocess, "run", return_value=ok) as run:
            second.ask("sonnet", "continue")
            self.assertIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])
            now[0] += r.dt.timedelta(hours=1)
            second.ask("haiku", "back to subscription")
            self.assertNotIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])
            self.assertNotIn("--max-budget-usd", run.call_args.args[0])
        self.assertEqual(self.ledger().remaining(), Decimal("4.6"))

    def test_reset_metadata_iso_epoch_and_unknown(self):
        now = r.dt.datetime(2026, 11, 19, 17, tzinfo=r.dt.timezone.utc)
        expected = now + r.dt.timedelta(hours=2)
        for value in (expected.isoformat(), int(expected.timestamp())):
            self.assertEqual(r.subscription_reset({"error": {"resets_at": value}}, "", now), expected)
        self.assertEqual(r.subscription_reset("Usage limit resets at 2026-11-19T19:00:00Z", "", now), expected)
        self.assertIsNone(r.subscription_reset("usage limit", "", now))

    def test_auto_caps_and_api_limits_never_retry(self):
        limit = subprocess.CompletedProcess([], 1, '{"is_error":true,"result":"usage limit","reset_at":"2099-01-01T00:00:00Z"}', "")
        for daily in ("0", "5"):
            self.path.unlink(missing_ok=True)
            client = r.Claude("fake", None, auth="auto", ledger_factory=lambda: self.ledger(daily=daily))
            with patch.object(r.subprocess, "run", return_value=limit) as run, self.assertRaises(r.Stop):
                client.ask("sonnet", "hello")
            self.assertEqual(run.call_count, 1 if daily == "0" else 2)
        # A pending API reservation must not prevent a fresh subscription call.
        client = r.Claude("fake", None, auth="auto", ledger_factory=self.ledger)
        ok = subprocess.CompletedProcess([], 0, '{"result":"ok"}', "")
        with patch.object(r.subprocess, "run", return_value=ok):
            self.assertEqual(client.ask("haiku", "hello"), "ok")

    def test_auto_does_not_fallback_on_other_failures_or_without_key(self):
        for auth, key, message in (("auto", "fake", "connection failed"),
                                   ("auto", None, "usage limit"),
                                   ("subscription", "fake", "usage limit")):
            client = r.Claude(key, None, auth=auth, ledger_factory=self.ledger)
            fail = subprocess.CompletedProcess([], 1, json.dumps({"is_error": True, "result": message}), "")
            with patch.object(r.subprocess, "run", return_value=fail) as run, self.assertRaises(r.Stop):
                client.ask("sonnet", "hello")
            self.assertEqual(run.call_count, 1)
        self.assertFalse(self.path.exists())

    def test_auto_default_main_uses_subscription_despite_key_and_exhausted_cap(self):
        home = self.root / "home"
        home.mkdir()
        key = home / r.KEY_NAME
        key.write_text("fake")
        key.chmod(0o600)
        ledger = r.Ledger(home / "usage.json", "5", "100")
        self.charge(ledger, "5")
        calls = []
        def run(cmd, **kw):
            if cmd[:3] == ["claude", "auth", "status"]:
                return subprocess.CompletedProcess(cmd, 0, '{"authMethod":"claude.ai"}', "")
            if cmd[:2] == ["gh", "api"]:
                return subprocess.CompletedProcess(cmd, 0, "volunteer", "")
            if cmd[:2] == ["claude", "-p"]:
                calls.append(kw["env"])
                return subprocess.CompletedProcess(cmd, 0, '{"result":"ok"}', "")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        def batch(controller, model, steps):
            controller.claude.issue = 123
            controller.claude.start_triage(123, True)
            controller.claude.ask("sonnet", "hello")
            return True
        with patch.object(r, "ROOT", self.root), patch.object(r, "HOME_STATE", home), patch.object(r.shutil, "which", return_value="fake"), patch.object(r.subprocess, "run", side_effect=run), patch.object(r, "batch", side_effect=batch), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(r.main([]), 0)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("ANTHROPIC_API_KEY", calls[0])
        self.assertIn("Triage #123: subscription; API cost: $0.000000", output.getvalue())
        self.assertEqual(len(json.loads((home / "usage.json").read_text())["runs"]), 1)

    def test_reset_state_without_key_still_uses_subscription(self):
        state = self.root / "subscription.json"
        state.write_text('{"reset_at":"2099-01-01T00:00:00+00:00"}')
        client = r.Claude(None, None, auth="auto", state_path=state)
        ok = subprocess.CompletedProcess([], 0, '{"result":"ok"}', "")
        with patch.object(r.subprocess, "run", return_value=ok) as run:
            self.assertEqual(client.ask("sonnet", "hello"), "ok")
        self.assertNotIn("--bare", run.call_args.args[0])

    def test_unknown_reset_rechecks_subscription_and_success_text_is_not_a_limit(self):
        client = r.Claude("fake", None, auth="auto", ledger_factory=self.ledger)
        limit = subprocess.CompletedProcess([], 1, "You've hit your limit", "")
        api = subprocess.CompletedProcess([], 0, '{"total_cost_usd":0.1,"result":"ok"}', "")
        ok = subprocess.CompletedProcess([], 0, '{"result":"Explain the usage limit to the user"}', "")
        with patch.object(r.subprocess, "run", side_effect=[limit, api, ok]) as run:
            client.ask("sonnet", "hello")
            self.assertIn("usage limit", client.ask("sonnet", "hello again"))
        self.assertEqual(["ANTHROPIC_API_KEY" in c.kwargs["env"] for c in run.call_args_list], [False, True, False])

    def test_forced_api_ignores_subscription_reset_and_stops_on_api_limit(self):
        state = self.root / "subscription.json"
        state.write_text("invalid irrelevant state")
        client = r.Claude("fake", self.ledger(), auth="api", state_path=state)
        limit = subprocess.CompletedProcess([], 1, '{"total_cost_usd":0.1,"is_error":true,"result":"credit balance too low"}', "")
        with patch.object(r.subprocess, "run", return_value=limit) as run, self.assertRaises(r.Stop):
            client.ask("sonnet", "hello")
        self.assertEqual(run.call_count, 1)
        self.assertIn("ANTHROPIC_API_KEY", run.call_args.kwargs["env"])
        self.assertEqual(self.ledger().remaining(), Decimal("4.9"))

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
            return subprocess.CompletedProcess(cmd, 0, "volunteer\n" if cmd[:2] == ["gh", "api"] else '{"authMethod":"claude.ai"}', "")

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

    def test_summary_uses_settled_costs_and_persisted_triage_counts(self):
        ledger = self.ledger()
        self.charge(ledger, "0.25")  # Haiku/maintenance overhead is included
        self.assertIn("n/a (no full triages started)", ledger.summary())
        ledger.start_triage(123, True)
        self.charge(ledger, "0.75")
        self.assertIn("$ per triage: $1.000000", self.ledger().summary())
        self.assertIn("$ per triage: $0.750000", ledger.summary(1, 0))
        ledger.reserve("sonnet")
        self.assertIn("unresolved reservation (cost unknown)", ledger.summary())
        self.assertTrue(json.loads(self.path.read_text())["triages"][0]["dry_run"])

    def test_cache_prefix_and_hour_ttl_on_every_api_call(self):
        client = r.Claude("fake", self.ledger())
        client.prefix = "unchanging kit docs"
        fake = subprocess.CompletedProcess([], 0, '{"total_cost_usd":0.1,"result":"ok"}', "")
        with patch.dict(os.environ, {"FORCE_PROMPT_CACHING_5M": "1", "DISABLE_PROMPT_CACHING": "1"}), patch.object(r.subprocess, "run", return_value=fake) as run:
            for model, issue in (("haiku", "123"), ("sonnet", "124")):
                client.ask(model, issue)
                cmd = run.call_args.args[0]
                self.assertEqual(cmd[cmd.index("--system-prompt") + 1], "unchanging kit docs")
                self.assertEqual(run.call_args.kwargs["input"], issue)
                env = run.call_args.kwargs["env"]
                self.assertEqual(env["CLAUDE_CODE_PROMPT_CACHE_TTL"], "1h")
                self.assertEqual(env["ENABLE_PROMPT_CACHING_1H"], "1")
                self.assertNotIn("FORCE_PROMPT_CACHING_5M", env)
                self.assertNotIn("DISABLE_PROMPT_CACHING", env)
        self.assertNotIn("CLAUDE_CODE_PROMPT_CACHE_TTL", r.model_env(None))

    def gate_result(self):
        return json.dumps(dict(attached_file=True, human_answered=False, duplicate=False))

    def prepare_batch(self, numbers=(123, 124)):
        controller = self.controller()
        controller.max_triages = 2
        (self.root / "state/cases").mkdir(parents=True, exist_ok=True)
        events = []
        def kit(args):
            events.append(tuple(args))
            if args[0] == "inbox":
                output = "\n".join(f"#{n} report" for n in numbers)
            else:
                output = "0 work items"
            if args[0] == "claim":
                controller.claims.add(args[1])
            if args[0] == "unclaim":
                controller.claims.discard(args[1])
            if args[0] == "case":
                (self.root / f"state/cases/{args[1]}.json").write_text(json.dumps({"number": int(args[1]), "attachment_present": True, "dup_candidates": [{"number": 90}]}))
            return json.dumps({"exit_code": 0, "output": output})
        return controller, kit, events

    def test_haiku_skips_each_ineligible_class_before_sonnet(self):
        for field, value in (("attached_file", False), ("human_answered", True), ("duplicate", True)):
            with self.subTest(field=field):
                controller, kit, events = self.prepare_batch()
                verdict = {"attached_file": True, "human_answered": False, "duplicate": False, field: value}
                with patch.object(r, "instructions", return_value="static"), patch.object(controller, "kit", side_effect=kit), patch.object(controller, "thread", return_value="thread"), patch.object(controller.claude, "ask", return_value=json.dumps(verdict)) as ask, contextlib.redirect_stdout(io.StringIO()):
                    self.assertTrue(r.batch(controller, "haiku", 10))
                self.assertTrue(all(c.args[0] == "haiku" for c in ask.call_args_list))
                self.assertFalse(any(e[0] == "case" for e in events))
                self.assertEqual(controller.triages, 0)

    def test_duplicate_case_gate_prevents_sonnet_and_releases_claim(self):
        controller, kit, events = self.prepare_batch((123,))
        duplicate = json.dumps({"attached_file": True, "human_answered": False, "duplicate": True})
        with patch.object(r, "instructions", return_value="static"), patch.object(controller, "kit", side_effect=kit), patch.object(controller, "thread", return_value="thread"), patch.object(controller.claude, "ask", side_effect=[self.gate_result(), duplicate]) as ask, contextlib.redirect_stdout(io.StringIO()):
            r.batch(controller, "haiku", 10)
        self.assertEqual([c.args[0] for c in ask.call_args_list], ["haiku", "haiku"])
        self.assertIn('"dup_candidates"', ask.call_args_list[-1].args[1])
        self.assertIn(("case", "123", "--no-images"), events)
        self.assertFalse(controller.claims)
        self.assertEqual(controller.triages, 0)

    def test_sequential_triages_and_cap_even_if_inbox_returns_extra(self):
        controller, kit, events = self.prepare_batch()
        controller.max_triages = 1
        controller.claude.ledger = self.ledger()
        done = json.dumps({"action": "done", "notes": "done", "selfcheck": {}})
        with patch.object(r, "instructions", return_value="static docs"), patch.object(controller, "kit", side_effect=kit), patch.object(controller, "thread", return_value="thread") as thread, patch.object(controller.claude, "ask", side_effect=[self.gate_result(), self.gate_result(), done]) as ask, contextlib.redirect_stdout(io.StringIO()):
            r.batch(controller, "haiku", 10)
        self.assertEqual(thread.call_count, 1)
        self.assertEqual(controller.triages, 1)
        self.assertEqual(len(self.ledger().data["triages"]), 1)
        self.assertEqual([c.args[0] for c in ask.call_args_list], ["haiku", "haiku", "sonnet"])
        self.assertEqual(controller.claude.prefix, "static docs")
        self.assertFalse(controller.claims)

    def test_host_refuses_unscreened_issue_and_repro_handoff(self):
        controller = self.controller()
        controller.active_issue = 123
        for action in ({"action": "kit", "args": ["case", "124"]},
                       {"action": "kit", "args": ["wantrepro", "124"]},
                       {"action": "kit", "args": ["next"]},
                       {"action": "write", "path": "state/cases/124.comment.md", "text": "x"}):
            with self.subTest(action=action), self.assertRaises(r.Stop):
                controller.action(action)

    def test_plan_defaults_overrides_and_dry_run_cost_summary(self):
        home = self.root / "home"
        home.mkdir()
        key = home / r.KEY_NAME
        key.write_text("fake")
        key.chmod(0o600)
        seen = []
        def batch(controller, model, steps):
            ledger = controller.claude.ledger
            seen.append((ledger.daily, ledger.total, controller.max_triages))
            ledger.start_triage(123, controller.dry)
            self.charge(ledger, "0.625")
            controller.previews = 1
            return True
        def run(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 0, "volunteer\n", "")
        with patch.object(r, "ROOT", self.root), patch.object(r, "HOME_STATE", home), patch.object(r.shutil, "which", return_value="fake"), patch.object(r.subprocess, "run", side_effect=run), patch.object(r, "batch", side_effect=batch), contextlib.redirect_stdout(io.StringIO()) as output:
            for args in ([], ["--plan", "max200"], ["--budget-usd", "2", "--plan", "max200", "--total-budget-usd", "30", "--max-triages", "3"]):
                self.assertEqual(r.main(["--auth", "api", *args, "--dry-run"]), 0)
        self.assertEqual(seen, [(Decimal(5), Decimal(100), 10), (Decimal(10), Decimal(200), 10), (Decimal(2), Decimal(30), 3)])
        self.assertEqual(output.getvalue().count("DRY RUN batch ledger: $0.625000"), 3)
        self.assertIn("$ per triage: $0.625000", output.getvalue())
        self.assertIn(r.SPEND_LIMITS, output.getvalue())
        self.assertIn("overshoot", output.getvalue())

    def test_invalid_triage_caps_fail_before_child(self):
        for cap in ("0", "-1"):
            with patch.object(r, "HOME_STATE", self.root), patch.object(r.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(r.main(["--max-triages", cap]), 1)
                run.assert_not_called()


    def test_malformed_haiku_gate_stops_and_releases_claim(self):
        controller, kit, events = self.prepare_batch((123,))
        with patch.object(r, "instructions", return_value="static"), patch.object(controller, "kit", side_effect=kit), patch.object(controller, "thread", return_value="thread"), patch.object(controller.claude, "ask", return_value="[]") as ask, contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(r.Stop, "Malformed Haiku"):
            r.batch(controller, "haiku", 10)
        self.assertEqual(ask.call_count, 1)
        self.assertFalse(controller.claims)
        self.assertEqual(controller.triages, 0)

    def test_failed_claim_never_starts_any_model(self):
        controller, kit, events = self.prepare_batch((123,))
        def failed_claim(args):
            if args[0] == "claim":
                return json.dumps({"exit_code": 1, "output": "already claimed elsewhere"})
            return kit(args)
        with patch.object(r, "instructions", return_value="static"), patch.object(controller, "kit", side_effect=failed_claim), patch.object(controller.claude, "ask") as ask, contextlib.redirect_stdout(io.StringIO()):
            r.batch(controller, "haiku", 10)
        ask.assert_not_called()
        self.assertEqual(controller.triages, 0)

    def test_two_issues_finish_back_to_back_in_one_batch(self):
        controller, kit, events = self.prepare_batch()
        calls = []
        def ask(model, prompt):
            calls.append((model, prompt, controller.active_issue))
            if model == "haiku":
                return self.gate_result()
            return json.dumps({"action": "done", "notes": "done", "selfcheck": {}})
        with patch.object(r, "instructions", return_value="static docs") as docs, patch.object(controller, "kit", side_effect=kit), patch.object(controller, "thread", return_value="thread"), patch.object(controller.claude, "ask", side_effect=ask), contextlib.redirect_stdout(io.StringIO()):
            r.batch(controller, "haiku", 10)
        self.assertEqual([m for m, _, _ in calls], ["haiku", "haiku", "sonnet", "haiku", "haiku", "sonnet"])
        self.assertEqual([n for m, _, n in calls if m == "sonnet"], [123, 124])
        self.assertNotIn('"number": 123', calls[-1][1])
        self.assertEqual(controller.triages, 2)
        docs.assert_called_once_with(self.root)

    def test_file_must_be_present_even_if_haiku_approves(self):
        controller, kit, events = self.prepare_batch((123,))
        def no_file(args):
            value = kit(args)
            if args[0] == "case":
                (self.root / "state/cases/123.json").write_text('{"attachment_present":false}')
            return value
        with patch.object(r, "instructions", return_value="static"), patch.object(controller, "kit", side_effect=no_file), patch.object(controller, "thread", return_value="thread"), patch.object(controller.claude, "ask", return_value=self.gate_result()) as ask, contextlib.redirect_stdout(io.StringIO()):
            r.batch(controller, "haiku", 10)
        self.assertTrue(all(c.args[0] == "haiku" for c in ask.call_args_list))
        self.assertEqual(controller.triages, 0)
        self.assertFalse(controller.claims)

    def test_reproduction_handoff_requires_a_file_on_host(self):
        controller = self.controller()
        path = self.root / "state/cases/123.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"attachment_present":false}')
        with patch.object(r.subprocess, "run") as run, self.assertRaisesRegex(r.Stop, "attached file"):
            controller.kit(["wantrepro", "123"])
        run.assert_not_called()
        path.write_text('{"attachment_present":true}')
        fake = subprocess.CompletedProcess([], 0, "handed off", "")
        with patch.object(r.subprocess, "run", return_value=fake) as run, contextlib.redirect_stdout(io.StringIO()):
            controller.kit(["wantrepro", "123"])
        self.assertEqual(run.call_count, 1)

    def test_legacy_ledger_counts_are_not_invented(self):
        self.path.write_text(json.dumps({"runs": [{"usd": "1", "day": "2026-11-19"}]}))
        ledger = self.ledger()
        self.assertEqual(ledger.remaining(), Decimal(4))
        ledger.start_triage(123, True)
        self.charge(ledger, "0.2")
        self.assertIn("n/a (legacy usage lacks triage counts)", ledger.summary())
        self.assertIn("$ per triage: $0.200000", ledger.summary(1))

    def test_stopped_dry_batch_still_prints_measured_cost_summary(self):
        home = self.root / "home"
        home.mkdir()
        key = home / r.KEY_NAME
        key.write_text("fake")
        key.chmod(0o600)
        def batch(controller, model, steps):
            ledger = controller.claude.ledger
            ledger.start_triage(123, True)
            self.charge(ledger, "0.31")
            raise r.Stop("Action limit reached")
        fake = subprocess.CompletedProcess([], 0, "volunteer", "")
        with patch.object(r, "ROOT", self.root), patch.object(r, "HOME_STATE", home), patch.object(r.shutil, "which", return_value="fake"), patch.object(r.subprocess, "run", return_value=fake), patch.object(r, "batch", side_effect=batch), contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(r.main(["--auth", "api", "--dry-run"]), 1)
        self.assertIn("DRY RUN batch ledger: $0.310000", output.getvalue())
        self.assertIn("$ per triage: $0.310000", output.getvalue())
        self.assertFalse((self.root / "state/runner-dry-run-volunteer.json").exists())

    def test_maintenance_runs_without_opening_unscreened_triages(self):
        controller, kit, events = self.prepare_batch(())
        def with_followup(args):
            if args[0] == "followups":
                return json.dumps({"exit_code": 0, "output": "#99 a reply | FILE"})
            return kit(args)
        done = json.dumps({"action": "done", "notes": "checked old reply", "selfcheck": {}})
        with patch.object(r, "instructions", return_value="static"), patch.object(controller, "kit", side_effect=with_followup), patch.object(controller.claude, "ask", return_value=done) as ask, contextlib.redirect_stdout(io.StringIO()):
            r.batch(controller, "haiku", 10)
        self.assertEqual(ask.call_count, 1)
        self.assertIn("Maintenance only", ask.call_args.args[1])
        self.assertEqual(controller.triages, 0)
        with self.assertRaises(r.Stop):
            controller.action({"action": "kit", "args": ["claim", "99"]})


if __name__ == "__main__":
    unittest.main()
