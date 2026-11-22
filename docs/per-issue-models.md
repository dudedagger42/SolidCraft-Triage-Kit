# Which model for per-issue runs

A short profile of running the kit's first pass (one fresh run per issue, `dispatch --per-issue`) on a cheap model and
on a stronger one. Use it to choose a model for each lane.

## What was measured

20 issues the kit had already answered live, each run once per model in per-issue mode, as a dry run (nothing posted).
The case file was cut back to what a first pass sees: the kit's own earlier comments and everything after them, the
"in progress" label and the other-triage flag removed. The earlier answer in the kit's `posted.jsonl` is the ground
truth. An issue the live kit marked "reproduced" counts as right when the first pass says `needs_repro`, because a later
stage did the reproducing. Fixed-on-main is not covered (the ledger has no such verdict).

| | Cheap model | Stronger model |
|---|---|---|
| Agrees with the live verdict | 14/20 (70%) | 15/20 (75%) |
| needs_info | 4/5 | 4/5 |
| feature_note | 3/4 | 2/4 |
| duplicate | 3/5 | 5/5 |
| support_answer | 0/2 | 0/2 |
| needs_repro (live: reproduced) | 4/4 | 4/4 |
| Cost per issue (as reported by each run) | $0.016 | $0.193 |
| Turns per issue | 12.8 | 12.8 |
| Wall time per issue | 50 s | 29 s |

The cheap model is about 12 times cheaper; the stronger one is faster on the clock. With 20 issues the 70% against 75%
gap is noise. The real differences are cost and duplicates.

## Where each one fails

- The cheap model misses duplicates. Two issues the live kit called duplicates became "needs_info" because it answered
  the checklist without following the near-duplicate hit in the case file.
- The stronger model is not clean on feature requests: one feature note became a duplicate.
- Both fail support questions the same way: they say needs_repro, needs_info or no_action instead of answering a how-to
  from the facts in the case.
- Both sent one needs_info report to needs_repro, and both missed a request that belongs to a sibling project.
- No run failed to finish, crashed, or tried to post.

## Recommendation

A cheap model classifies; a stronger model writes anything public.

- Run the first pass on the cheap model: needs_info, feature_note, easy routing, and the no_action calls.
- Hand the issue to the stronger model when the cheap one says needs_info or no_action, when the case lists a
  duplicate candidate, or when the verdict would post a duplicate or a support answer. A wrong call is costly there,
  and those comments are public.
- Keep a stronger model on the reproducer and audit lanes.
- The kit's `decide` step and its lint blocks already catch many bad outputs, so the cheap model's mistakes mostly stop
  before posting. Stronger-model-only is the safe fallback and is still cheap.

`dispatch --kinds new` runs only first passes, so one dispatcher can be the cheap lane while another takes follow-ups
and reproducers with a stronger model. `--output-dir` keeps each run's full output for comparing the two.

## Cost per 100 issues

| Option | Per 100 issues | $200 buys |
|---|---|---|
| Cheap model only | $1.58 | about 12,700 issues |
| Stronger model only | $19.34 | about 1,030 issues |
| Cheap, then stronger on about 40% (escalated) | about $9.30 | about 2,150 issues |
| Cheap first, stronger on duplicates only (about 15%) | about $4.50 | about 4,400 issues |

Reproducer and audit lanes are extra and not in these numbers. Costs are what each run reported with the kit's per-issue
context; they drift with thread length.
