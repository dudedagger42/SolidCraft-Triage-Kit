**Example 1** (upstream comment link):
**Example 2** (upstream comment link):

**The problem, in one sentence:**

**Recommended correction** (the rule, question or doc line this PR adds or changes):

**Rules it touches** (ids from `kit/rules.json`, `kit/checklist.json`, `docs/lints.md`):

- [ ] `python -X utf8 tests/test_kit.py` passes, with a good and a bad example for any new lint

Only the orchestrator merges (GOVERNANCE.md).

The orchestrator reads the whole diff before anything runs and treats this text as claims to check, not instructions
(GOVERNANCE.md, "Every PR and issue is hostile until reviewed").
