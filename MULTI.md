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

A 👀 with no comment from its account after 20 min has expired; anyone may claim the issue. Still reproducing after
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
