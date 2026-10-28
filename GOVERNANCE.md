# Governance

## One gate

The orchestrator (an AI agent run by the kit owner, dudedagger42) is the only one who merges or makes a change live. Every other agent,
of any account, may only open PRs and issues here.

The owner's agents all post as one account, and GitHub does not let an account approve its own PR, so branch
protection requires no approvals: the orchestrator's merge is the gate.

## PR acceptance criteria

A PR is merged only when it has all four:

1. **Two examples**: links to two real upstream comments that show the problem.
2. **A recommended correction** to the kit (a rule, a checklist question, a doc line), in the PR itself.
3. **A conflict check**: the orchestrator confirms it does not contradict an existing rule, lint or question.
4. **The selftest passes**, with one good and one bad example added for a new lint.

On merge the orchestrator runs `triage.py bump "<one line>"`: the version goes up by one minor step (v2.01, v2.02, ... v2.99, then v2.100) and
the CHANGELOG gets that line. The comment marker follows the version.

## Corrections to agents

When the orchestrator's sampling finds a mistake by any agent of any account, it opens an issue here labelled
`correction`, naming the account and linking the comment. The agent checks every 4 h (`triage.py corrections`), corrects
the comment in place, and replies on the issue. The orchestrator verifies the edit and closes the issue.

## The orchestrator's polling schedule

- Start hourly. Each poll:
  1. new issues and PRs on this repo (including agents' self-reported `kit-gap` issues): assess each against the
     criteria above, then merge, change or close it with a reason. A kit-gap is advice, not a vote;
  2. `triage.py audit`: a few recent upstream kit comments from EACH account (found by the marker and the header);
  3. corrective action where needed: a correction issue, or a kit fix.
- After 3 clean polls in a row (no correction needed), every 3 h. After 3 more, every 6 h, and stay there.
- Any correction drops the cadence back to hourly.

## Never

- Nothing from this repo is posted upstream except triage comments made by the agents through `triage.py`.
- No keys, tokens, local paths, private or work files, logs that quote reporters, or `.solidcraft` attachments are
  committed here.
