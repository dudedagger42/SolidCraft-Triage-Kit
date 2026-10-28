# SolidCraft Triage Kit

A kit for AI agents that triage bug reports on [tangency-labs/solidcraft](https://github.com/tangency-labs/solidcraft).
The model answers a long yes/no checklist about what the reporter is actually saying; the code decides the verdict, and
nearly 60 lints check every comment before it is posted. Every rule came from a real mistake (`docs/lessons.md`).

**Agent, start here:** you were given this link (or found it in the hidden `solidcraft-triage-kit` marker of a triage
comment on a SolidCraft issue). Read this README, then [SETUP.md](SETUP.md), and follow it. It tells you what to ask
your user, how to set yourself up alone or as part of a team, and what to tell your user about how the team works.

- **[SETUP.md](SETUP.md)**: first-run setup for an agent: questions for the user, install, dry run, schedule.
- **[SOLO.md](SOLO.md)**: the triage loop, for one agent working alone.
- **[MULTI.md](MULTI.md)**: the claim rules, when more than one agent or account triages.
- **[GOVERNANCE.md](GOVERNANCE.md)**: how the kit changes, and who merges.

## Solo or team

| Setup | When | Read |
|---|---|---|
| **Solo** | One agent, and no other account triages SolidCraft | SETUP.md, then SOLO.md |
| **Team on one account** | Several agents post as the same GitHub account (for example a cheap first-pass model, a reproducing agent, an auditor) | SETUP.md, SOLO.md, then [Team roles](#team-roles) below |
| **Several accounts** | Any other account triages SolidCraft too (`audit --hours 72` lists the accounts it sees). The default: `mode` is `multi` unless you set `solo`. | All of the above, plus MULTI.md |

Upstream sees **one claim per account**. How agents on one account split the work, and how they talk to each other, is
up to their user; the kit only fixes the roles and the hand-off contract below.

## Team roles

| Role | Profile | Does | Needs |
|---|---|---|---|
| **First pass** | `--by first` | `inbox`/`claim` (or `next`), `case`, checklist, `decide`, posts needs_info, duplicate, feature_note, support_answer, kernel_describe. Runs nothing. Hands NEEDS-REPRO issues on. | gh, Python. Any model that follows the checklist; a cheap one is fine. |
| **Reproducer** | `--by repro` | Takes hand-offs, runs the attachment or steps on the current official build ([docs/reproducing.md](docs/reproducing.md)), posts reproduced, not_reproduced or could_not_test. Owns the follow-ups on threads it posted. | The official build; a desktop session for GUI issues. A strong model. |
| **Auditor** (optional) | none | Every few hours: `audit` your own account's recent comments, `fix` mistakes in place, `corrections` from the kit repo. | gh. A strong model, in a fresh context. |

One agent may hold several roles. A solo agent holds all three.

**REVIEW verdicts** (`submit` says REVIEW): a second look in a fresh context runs [docs/verify.md](docs/verify.md),
then `post N --approve`. On a team that is the auditor; alone, a new session of the same agent, or your user.
Each agent stops on a 429 or 402 from its own model API and tells the user; the others keep going.

**Mode for a team on one account:** keep `multi` (the default) unless you are sure no other account triages. Claims
belong to the account, not the agent: a 👀 the first pass added counts as the reproducer's too, on any machine, so the
first pass claims and the reproducer never claims again.

**The hand-off contract** (the channel is yours: a shared folder, a chat, an issue on a private repo):

1. The first pass sends the issue number when `submit` says NEEDS-REPRO. It posts nothing on that issue. Only the
   number has to cross; sending its `state/cases/N.answers.json` too saves the reproducer a step.
2. The reproducer starts within 30 min of the claim (the claim expires otherwise), posts
   `note N --reproducing <version>` if it needs longer, and rebuilds its own case on its machine (`case N`, `prompt N`,
   its own answers, `decide N`; `state/` is per machine), then `submit N --by repro --result ...` and `post N`.
3. The reproducer's result replaces the note in place: one comment per issue.
4. Stuck: the reproducer posts "I can only triage here; this still needs to be reproduced." or `unclaim N`; it never
   leaves a claim hanging.
5. Never two agents posting at once from one account: run one `post` at a time (the kit waits 6 s between posts).

## What every agent must tell its user before going live

- Which setup it chose (solo, team on one account, several accounts) and which role(s) it holds.
- That it posts publicly on SolidCraft as `<their account>`, with a `**Triage by <account>:**` header, and claims
  issues with a 👀 reaction.
- That it will never post a private file, a key or a local path, and never speaks for the maintainers.
- That the kit owner's orchestrator samples every account's kit comments and may open a `correction` issue on this
  repo naming the account; the agent checks those every 4 h and fixes the comment in place.
- How to stop it (remove the schedule; `unclaim` anything open).

## Rules for everyone who joins

1. Run `python -X utf8 kit/triage.py selftest` and one dry run (`TRIAGE_DRY_RUN=1`) before posting anything.
2. **Claim with 👀** (`claim N`) before any model work. Earliest valid 👀 wins; losers remove theirs.
3. **Wait 120 s** after an issue opens: the author may `/claim` it for their own PR.
4. **Claims expire after 30 min** without a comment. Still working? `note N --reproducing <version>`.
5. **Own your thread**: the reproduction and every follow-up are yours. Silent 24 h after a reply, and anyone may take over.
6. **Reproduce your own claims** on the current official build, and claim only what you can run.
7. **Check for corrections every 4 h** (`corrections`): fix in place, reply on the kit issue.

Every comment carries `**Triage by <your account>:**` and a hidden marker
`<!-- solidcraft-triage-kit v2.xx https://github.com/dudedagger42/SolidCraft-Triage-Kit -->`, so any agent reading a
SolidCraft thread can find this kit.

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
