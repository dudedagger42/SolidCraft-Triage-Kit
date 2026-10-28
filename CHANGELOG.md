# Changelog

One line per merged change. Every merge bumps the minor version by one, two digits (2.01 ... 2.99, then 2.100) (`triage.py bump`); the comment marker follows it.

- v2.02 (2026-10-28): two-digit versions (2.01 ... 2.99, then 2.100); audit lints an appended translation apart; G03 accepts full-width endings; R027 checks the whole comment, not each line (false positives on #7678)
- v2.01 (2026-10-28): SETUP.md and team roles in the README; self-assessment (audit --mine, kit-gap issues); dry run blocks every GitHub write and prints the comment; kit URL in the marker; fixes from the first blind solo and team tests
- v2.00 (2026-10-28): first public version. The model answers a yes/no checklist and the code decides the verdict;
  MULTI.md claim rules (👀, 120 s author window, 30 min expiry, ownership, duplicate guard); kit marker in every comment;
  signature lint (the header is built from the posting account; no signature in the text); dynamic current-release
  lint; private-name and local-path lints; grammar lints for garbled edits; corrections as kit-repo issues. Rules and
  lessons carried over from v1 (never published).
