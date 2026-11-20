---
name: solidcraft-triage-kit
description: Set up or reconfigure the SolidCraft triage kit when a user asks their agent to configure triage, choose subscription and API budgets, preview comments, or schedule unattended runs.
---

Use the checkout containing this skill (the repository is two directories above this file).
Read `SETUP.md`, `docs/runner.md`, and `docs/hostile-input.md` there before setup.
This skill works with Claude Code and other agents that can read Agent Skills. The user's agent
configures the kit; `kit/run` uses Claude Code for bounded first-pass triage. No reproduction is claimed.

## Ask for the setup choices

Ask together, keeping any choices the user already supplied:

- Which GitHub account will post? Solo or multi-account/team claim mode? Any existing posting workers?
- Do they have a Claude Code subscription, and is it logged in? Do they also have API credits,
  and from which plan (Max $100, Max $200, or another allowance)? Confirm the actual Console balance.
- Use both tiers (`--auth auto`, default), subscription only, or API only?
- Daily USD cap (UTC day), total USD cap, and maximum full triages per batch?
  Offer `max100`: $5/day, $100 total; `max200`: $10/day, $200 total; 10 triages per batch.
  These are configurable caps, not a balance check. Dry runs consume model allowance too.
- Desired schedule and timezone (offer every 15 minutes), or manual runs only?
- Dry run first, then review before live scheduling? Explain that a completed comment preview and
  their approval are required before enabling live runs, even if they prefer to start live.

Resolve missing choices with the user before configuring spending or a live schedule. Explain the
first-pass/reproducer hand-off and the pre-live points in README. If the user wants a reproducer or
multiple workers, follow SETUP's team questions too; do not schedule competing workers on one account.

## Write local configuration and enter credentials

Check Python 3.11+, `gh`, and `claude`; check `gh api user --jq .login` and `claude auth status`.
Have the user log in with `gh auth login` / `claude auth login` when needed.

Merge the selected kit settings into ignored `state/config.local.json`, preserving unrelated values.
For example, start with `{"mode":"multi","dry_run":true}`. Do not change shared `kit/config.json`.
Save the selected runner flags in an executable, ignored `state/run-triage` shell script: use an absolute,
safely shell-quoted path to the checkout, `cd` there, then `exec` its `kit/run` with the user's
`--auth`, `--plan`, `--budget-usd`, `--total-budget-usd`, and `--max-triages` values and `"$@"`.
The runner reads kit settings from JSON; budget/auth flags belong in this wrapper, not the kit JSON.
Use this exact wrapper for previews and schedules so spending settings stay consistent.

For an API key, launch `kit/run --set-key` interactively in a terminal the user can type into directly.
The user enters the key at its hidden prompt. Never ask for it in chat, read the saved key, put it in
an agent tool argument, or capture terminal input. Do not source or print credential environments.
If your terminal tool cannot hand input directly to the user, have them run this command in their
own terminal; continue after it completes. The runner stores it outside the repo with mode 600.
Subscription-only users need no key. Explain auto: subscription first, capped API after a usage limit,
and subscription again at the reported reset. Force modes never switch tiers. Ask them to set the
Console organization spend limit as described in `docs/runner.md`.

## Preview before scheduling

Run `python3 -X utf8 kit/triage.py selftest`, then the local wrapper with `--dry-run`.
Show the proposed comments/verdicts, posting account, selected caps, per-issue tiers and API costs,
and any unresolved issues. A run with no completed comment preview does not qualify; keep it dry
and resolve the cause before proceeding. Never create a preview marker yourself.

Once the user has seen the preview, obtain their approval of the concrete live schedule/account/caps.
Keep `dry_run: true` until then. After approval, set it false and install the requested cron/systemd
or other available schedule calling the absolute wrapper path, with an absolute log path under `state/`.
Ensure the schedule's PATH includes `gh`, `claude`, and Python; use the requested timezone.
Verify the installed schedule and show how to disable it. Do not run a live batch just to verify a schedule.
For manual-only use, show the wrapper command; do not install a schedule.

## Adjust later

Explain which file owns each setting: kit claim/dry-run settings in `state/config.local.json`, auth,
plan/caps/max-triages in `state/run-triage`, and interval/timezone in their scheduler. Preserve the selected
caps on every scheduled call. To preview changes, set `dry_run: true` or pass `--dry-run`; review before
resuming live work. Stop by disabling the schedule (Ctrl-C for an active run). Unfinished claims can be
released with `python3 kit/triage.py unclaim N`. Never delete `~/.config/solidcraft-triage/usage.json`
to reset spend: see `docs/runner.md` for reconciling unresolved API usage. Total caps never reset;
subscription reset state is separate in `~/.config/solidcraft-triage/subscription.json`.
