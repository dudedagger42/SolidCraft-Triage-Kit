# Changelog

One line per merged change. Every merge bumps the minor version by one, two digits (2.01 ... 2.99, then 2.100) (`triage.py bump`); the comment marker follows it.

- v2.09 (2026-10-28): The "Triage by" header goes on the account's first comment in a thread only; replies, follow-ups and edits of a reply carry just the hidden marker (Gabe)
- v2.08 (2026-10-28): Reproducer wanted (MULTI.md 6a): `wantrepro N` ends your one comment with the can't-run line, pings up to two listed reproducers (reproducers.json) for the reporter's OS, adds 🚀 and drops your 👀; `inbox --repro` lists these for agents that can run SolidCraft; the first 👀 after the 🚀 claims, and its reproduction is the one other triage comment the duplicate guard allows. Claims now expire after 20 min (was 30).
- v2.07 (2026-10-28): Z01 (ask for the zip) no longer fights Z02 (no zip for GUI or crash reports); reported by DeepSeek's first v2 batch
- v2.06 (2026-10-28): a dry run leaves the queue and follow-up state as they were, so the live post can follow
- v2.05 (2026-10-28): M02: never ask for a screenshot or recording the thread already has; L03: a follow-up reply in another language needs reply --translation --language (both from the first v2 dry run)
- v2.04 (2026-10-28): a multi-mode dry run posts to the log when the issue is claimable (a dry run takes no claim)
- v2.03 (2026-10-28): dry run can be set in state/config.local.json ("dry_run": true), so a scheduled agent cannot forget the variable
- v2.02 (2026-10-28): two-digit versions (2.01 ... 2.99, then 2.100); audit lints an appended translation apart; G03 accepts full-width endings; R027 checks the whole comment, not each line (false positives on #7678)
- v2.01 (2026-10-28): SETUP.md and team roles in the README; self-assessment (audit --mine, kit-gap issues); dry run blocks every GitHub write and prints the comment; kit URL in the marker; fixes from the first blind solo and team tests
- v2.00 (2026-10-28): first public version. The model answers a yes/no checklist and the code decides the verdict;
  MULTI.md claim rules (👀, 120 s author window, 30 min expiry, ownership, duplicate guard); kit marker in every comment;
  signature lint (the header is built from the posting account; no signature in the text); dynamic current-release
  lint; private-name and local-path lints; grammar lints for garbled edits; corrections as kit-repo issues. Rules and
  lessons carried over from v1 (never published).
