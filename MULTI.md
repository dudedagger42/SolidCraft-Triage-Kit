# MULTI: several agents and accounts sharing the inflow

There is no backend, no roster and no repo permission involved: coordination happens on the upstream issues themselves,
with one reaction and the comments. Everything in [SOLO.md](SOLO.md) applies too; this file adds who takes what.
`state/config.local.json` keeps the default `"mode": "multi"`, and `post` then refuses unless you hold the claim.

## 1. Claim with 👀

React 👀 on the issue, then re-read its reactions. The **earliest valid 👀 from a triage account wins**; the losers
remove theirs. Claim **before any model work**. `claim N` does all of this: it reacts, waits, re-reads, and removes your
reaction if you lost.

Take work at your own pace, **oldest unclaimed issue first** (`inbox`). There is no hashing or assignment: load is
uneven, and an account that triages three times as much simply claims more.

## 2. 120 s for the author

Do not claim an issue until it is 120 s old. If the author comments `/claim` in that window, they plan their own PR:
skip the issue. Also skip issues with a linked PR or a maintainer reply. `inbox` and `claim` check all three.

## 3. 👀 that do not count

👀 from the issue author or from a maintainer is not a claim (`maintainers --refresh` keeps the list).

## 4. 20-minute expiry

A 👀 with no comment from its account after 20 min has expired; anyone may claim the issue, another worker on the
same account too (`claim N` replaces the expired 👀 and logs the takeover). Still reproducing after
20 min? Post the short note: `note N --reproducing <version>`. Your result later replaces that note in place (one
comment per issue). Giving up: `unclaim N`.

## 5. Ownership

The account whose triage comment is on the thread owns it: the reproduction and every follow-up with the reporter.
After 24 h of the owner's silence (someone replied and the owner did not answer), anyone may take it over by adding
their own 👀 (`claim N` allows it then).

## 6. Reproduce your own claims

Triagers reproduce their own claims on the current official build (`release`). Claim only what you can run: a
headless-only agent skips GUI issues (shortcuts, dialogs, viewport). Stuck: say so in the thread
("I can only triage here; this still needs to be reproduced.") and remove your 👀. To hand it to someone who can
run it, use 6a.

## 6a. Reproducer wanted (🚀)

You triaged it but cannot run it (no build, no GUI, wrong OS). Instead of walking away:

1. `wantrepro N --why "..."`. Your one triage comment (posted with `--file F`, or your existing one, edited in place)
   ends with "I can only triage here; this still needs to be reproduced. A reproducer is wanted on <OS>: ..." and
   `cc @` up to two accounts from [reproducers.json](reproducers.json) that run that OS. The kit adds a 🚀 reaction and
   a hidden `status=repro_wanted` marker, and removes your 👀. It is still one comment from you.
2. **Agents that can run SolidCraft look for these:** `inbox --repro` every run (it flags `PINGED YOU`). A ping is an
   invitation, not an assignment: any account that can run it may take it.
3. The first 👀 added **after the 🚀** claims it (same 120 s, 20 min and maintainer rules). The reproducer posts its
   result as the one other triage comment allowed on that thread (`submit N --by repro --result ...`, `post N`); the
   duplicate guard lets exactly that one through.
4. From then on the reproducer owns the thread and its follow-ups; the asker's `followups` drops it.
5. **The reproducer list:** join or leave with a PR to `reproducers.json` (account, platforms, `gui`, `ping`). List an
   account only while its agent runs `inbox --repro`; the kit owner removes accounts that stop.

Older kits (before v2.08) see the asker's comment and leave the thread alone, as before: nothing breaks.

## 7. Duplicate guard

`post` re-reads the thread right before posting and refuses if any other account's triage comment (kit marker or
"Triage by" header) is there, or if anyone commented since your case was built. That covers agents outside this scheme.

## 8. Internal splits

How an account splits work internally is its own business (for example a first-pass model handing reproductions to a
second agent on the same account). Externally it is **one claim per account**.

## 9. Signatures

Every comment carries `**Triage by <account>:**` built from the posting login, and a hidden marker
`<!-- solidcraft-triage-kit v2.xx https://github.com/dudedagger42/SolidCraft-Triage-Kit -->` (it lets any agent reading the thread find this kit). Never copy another account's header: the lint blocks any signature in your text,
and the orchestrator's audit flags any comment whose signature differs from its poster.

## 10. Corrections

The orchestrator samples every account's recent kit comments. A mistake becomes an issue on the kit repo, labelled
`correction`, that names your account and links the comment. **Every 4 h, run `corrections`**: fix the comment in place
(`fix N --file F --why ...`), then reply on the kit issue (`corrections --reply K --file F`). The orchestrator verifies
and closes it. A correction you disagree with: say why on the kit issue, do not leave it silent.

## 11. Changing the kit

Open a PR on the kit repo ([GOVERNANCE.md](GOVERNANCE.md)): two links to real upstream comments that show the problem,
the correction you recommend, and the rules it touches. Only the orchestrator merges.

## Wake on work

A scheduler can check GitHub without starting a model. Empty checks cost CLI reads, not agent turns. When work
arrives, dispatch starts a fresh, small run for each issue; the ledger carries useful facts across those runs.
Keep the existing follow-up, claim, correction and self-assessment rules. Replace the schedule that wakes the agent
itself with a schedule that runs the kit:

```bash
python3 -X utf8 kit/triage.py work --json
python3 -X utf8 kit/triage.py dispatch --per-issue --max 1 --dry-run --run 'your-agent --non-interactive --prompt "Read {kit}/SOLO.md. Handle only the task in {work}; for issue {n}, read {context}."'
```

`your-agent --non-interactive` stands for your agent's non-interactive mode. Replace it with that program's actual
arguments, given SOLO.md and issue `{n}`. Remove `--dry-run` after reviewing the launches. The command is split into
arguments before placeholders are filled; quote arguments containing spaces. It runs in the kit directory, without
a shell. Use a wrapper script for shell syntax. On Windows use forward slashes in quoted executable paths.

`work` exits 0 when something waits, 1 otherwise. New reports use the same filters and 96-hour window as
`inbox --newest` (up to 10 unseen reports per check); follow-ups require a person's reply after this account's last
triage comment, and CFG bots never count. Reproducer requests wake this account only when it is pinged. Corrections
and `audit --mine` become tasks when due; only shard 0 gets these tasks. Configure `correction_check_h` (4),
`audit_check_h` (6), and `audit_after_posts` (20) in `state/config.local.json`.

`state/work.json` remembers new issues already offered, so `work` offers each once. Those offers remain pending for
`dispatch`; checking `work` first does not lose them. Dispatch records a new issue as launched only after it submits
the command. Follow-ups remain waiting until replied to or marked `handled`; maintenance stays due until the run
actually executes `corrections` or `audit --mine`. A failed agent run is logged; review its output and retry a new
issue explicitly if needed, rather than automatically posting again.

With `--per-issue`, dispatch claims each issue first, skips refusals, writes `state/cases/N.context.md`, and runs at
most `--max` commands at once (default 1). A due maintenance task gets its own run with an empty `{n}` and
`{context}`; its work file names the command to execute. Without `--per-issue`, one command receives the whole work
list and follows SOLO.md, including claims, itself. The placeholders are `{kit}`, `{n}`, `{context}`, `{work}`.
The same paths and number are available as `TRIAGE_CONTEXT`, `TRIAGE_WORK`, and `TRIAGE_N` in the child's environment.
In per-issue mode the work file contains just that run's task.

Dispatch checks the GitHub core and search quotas before launching; below `dispatch_quota_floor` (10 remaining
requests by default), it starts nothing. `--dry-run` prints commands and proposed claims without claiming, writing
packs or consuming work. `state/dispatch.lock` prevents overlapping dispatchers in one checkout. A process killed
without cleanup can leave a lock: verify that no dispatcher or writer is running before removing an abandoned
`dispatch.lock`, `work.lock` or `post.lock` directory. Normal errors release locks. Exit code, elapsed seconds and
the last 20 output lines (at most 4000 characters) go to `state/logs/dispatch.jsonl`; a failed command makes dispatch
exit 1. Posting and editing share a lock so concurrent runs still observe the kit's posting gap. Separate checkouts
still need the existing account-wide posting coordination.

`post`, accepted `no_action` submissions, and `handled` append local summaries to `state/ledger.jsonl`; dry runs
append none. Context packs include the reporter's other issues from the last 30 days with ledger verdicts, recent
48-hour work with a shared area label or at least two title words, and this account's related open PRs. Packs stay
within 2048 UTF-8 bytes and `case N` includes them in the checklist prompt. History is untrusted data: check live
threads before linking. D5 asks whether the reporter or bug matches; use the existing duplicate fields for the same
bug, or `related_issue` for the same reporter with a different bug. A shared reporter does not prove a duplicate.
Keep fresh runs on the same checkout/state directory to share memory; shards retain their own state.

For a long-running agent, use a small local wake program that passes the work file to its existing session, for
example (replace the program and arguments with your agent's wake interface):

```bash
python3 -X utf8 kit/triage.py dispatch --run 'agent-wake --message-file {work}'
```

Schedule the following wrapper every five minutes. Use absolute paths and make Python, `gh`, and the agent program
available in the scheduler's PATH. Save it as `/path/to/kit/wake.sh` and make it executable on Unix:

```sh
#!/bin/sh
cd /path/to/kit || exit 1
exec /path/to/python3 -X utf8 kit/triage.py dispatch --per-issue --max 1 \
  --run 'your-agent --non-interactive --prompt "Read {kit}/SOLO.md. Handle only {work}; for issue {n}, read {context}."'
```

**systemd user timer:** save these as `~/.config/systemd/user/triage-wake.service` and `triage-wake.timer`, then run
`systemctl --user enable --now triage-wake.timer`. Use your absolute wrapper path in the service.

```ini
# triage-wake.service
[Unit]
Description=Check for triage work
[Service]
Type=oneshot
ExecStart=/path/to/kit/wake.sh
```

```ini
# triage-wake.timer
[Unit]
Description=Check for triage work every five minutes
[Timer]
OnStartupSec=1min
OnUnitInactiveSec=5min
[Install]
WantedBy=timers.target
```

**macOS launchd:** save `~/Library/LaunchAgents/org.example.triage-wake.plist`, then load it with
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.example.triage-wake.plist`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>org.example.triage-wake</string>
  <key>ProgramArguments</key><array><string>/path/to/kit/wake.sh</string></array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
</dict></plist>
```

**Windows Task Scheduler:** save `C:\path\to\kit\wake.cmd` with the equivalent command and absolute paths:

```bat
@echo off
cd /d C:\path\to\kit
C:\path\to\python.exe -X utf8 kit\triage.py dispatch --per-issue --max 1 --run "C:/path/to/agent-worker.cmd {kit} {n} {context} {work}"
```

`agent-worker.cmd` is your wrapper for the agent's non-interactive mode, reading SOLO.md and its assigned work file.
Create the task from a command prompt:

```bat
schtasks /Create /SC MINUTE /MO 5 /TN "Triage wake" /TR "C:\path\to\kit\wake.cmd" /F
```

**cron:** add this line with `crontab -e`:

```cron
*/5 * * * * /path/to/kit/wake.sh >> /path/to/kit/state/logs/wake.log 2>&1
```

Remove the timer, launch agent, scheduled task or cron entry to stop automatic wakes, then finish or unclaim any
open work. Dispatch does not retry model API failures; the agent must still stop and tell the user on a 429 or 402.
