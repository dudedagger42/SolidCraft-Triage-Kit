# SolidCraft Triage Kit

A kit for AI agents that triage bug reports on [tangency-labs/solidcraft](https://github.com/tangency-labs/solidcraft).
The model answers a long yes/no checklist about what the reporter is actually saying; the code decides the verdict, and
nearly 60 lints check every comment before it is posted. Every rule came from a real mistake (`docs/lessons.md`).

- **[SOLO.md](SOLO.md)**: one agent triaging alone.
- **[MULTI.md](MULTI.md)**: several agents and accounts sharing the inflow.
- **[GOVERNANCE.md](GOVERNANCE.md)**: how the kit changes, and who merges.

## How to join

1. Read [MULTI.md](MULTI.md) and run `python -X utf8 kit/triage.py selftest`.
2. **Claim with 👀** (`claim N`) before any model work. Earliest valid 👀 wins; losers remove theirs.
3. **Wait 120 s** after an issue opens: the author may `/claim` it for their own PR.
4. **Claims expire after 30 min** without a comment. Still working? `note N --reproducing <version>`.
5. **Own your thread**: the reproduction and every follow-up are yours. Silent 24 h after a reply, and anyone may take over.
6. **Reproduce your own claims** on the current official build, and claim only what you can run.
7. **Check for corrections every 4 h** (`corrections`): fix in place, reply on the kit issue.

Every comment carries `**Triage by <your account>:**` and the hidden marker `<!-- solidcraft-triage-kit v2.x -->`.

## Layout

| Path | What |
|---|---|
| `kit/triage.py` | The one CLI: claims, case, checklist prompt, decide, submit, post, fix, follow-ups, corrections, audit |
| `kit/checklist.json` | The checklist questions (the core) |
| `kit/rules.json` | Pattern lints; the code lints are listed in `docs/lints.md` |
| `kit/config.json` | Repo names, timings, skip labels (override in `state/config.local.json`) |
| `docs/` | The prompt, verify pass, lessons, importance, reproducing, UI features, duplicate clusters |
| `repro/` | `replay.py` (run a report's attachment on the official CLI), `sc.py` (app control channel) |
| `tests/test_kit.py` | Offline selftest of the decisions and lints |

Version: see `VERSION` and [CHANGELOG.md](CHANGELOG.md). License: MIT.
