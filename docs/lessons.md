# Lessons

Every rule in the kit came from a real mistake on a real issue. One line per lesson: what went wrong, and the rule or
lint it became. New lessons are appended by `triage.py corrective` or by a merged PR (GOVERNANCE.md).

## From v1 (October 2026), folded into v2

### Claims the triager could not back
- First-pass models said "reproduced", "I tested", "I ran" without running anything. Rule: the first pass runs nothing;
  a bug with steps or a file is `needs_repro` (R003, R004).
- "Can't download the attachment" excuses: zip and tar both extract fine with `repro/replay.py` (R008; E3 rejects it).
- Untested workarounds offered as advice. Rule: no workaround without `workaround_tested` (R005).
- "Logged as a feature request" on something `solid.hole` already does (#7625): nobody logged anything, and the app
  already had it (R026; K5/K6 make the app check part of the answer).
- "Fixed in <version>" stated from memory (R010; verify 21; lint V01 for retest versions).
- A test's name in a failure is not a compile error; read where the name lives before naming a cause (#7212).
- A reporter's "my PR fixes it" is a claim: check the PR's live state (#6747 was closed unmerged).
- A cause stated as fact from one phrase ("I made fillets" made it "fillet work", #7019) (R036; verify 14-19).

### Noise
- Thank-you and praise floods (R002, R006). Restating the report (R017). Speaking for the project (R001, R007).
- Repeating the bot's request for steps, version and OS: `bot_asked` plus no pointed question is `no_action` (decide).
- Asking the version, OS or GPU when the Environment block has it (#7320, #7323, #7365) (R022, R023, R025).
- Two or more questions in one comment (Q01). Generic "more details" requests (R029).
- About 15 identical "should this stay under #5921?" comments on a split-off family (R024).
- A bare "kernel work is paused (#3992)" with no question (#6514, #6531, #7624) (R027).
- One generic request on each report of a same-version crash cluster (decide: `crash_cluster`). Only empty ones: a crash report with the reporter's own steps goes to reproduction, and one with a real backtrace takes the normal path (v2.22, Gabe).

### Mechanical mistakes
- Mechanical rule edits that garbled sentences: a template fragment pasted mid-sentence, a doubled word, a dangling
  clause (R013, G01-G04). Re-read the whole comment after any edit.
- Asking for a bare `.solidcraft` file, which GitHub refuses: always say zip (R009, Z01).
- Asking for the design on crash, GUI and usage reports, where it does not help (Z02).
- Asking for a file already attached (R011).
- The translation written twice, once in the comment and once in the translation field (#6678) (R020).
- The header repeated inside a translation (#7473, #7458) (S01).
- "The case file shows..." and "the command list" in public comments (#7069, #6940) (R016, R018).
- Saying the app has no wireframe mode; it is a visual style, not a command (#6704) (R019).
- Describing screenshots that were never opened (#7118, #7119) (R015, `images_viewed`).
- Asking a reporter to retest on an old release after a new one shipped (#6839, #6830) (V01).
- "Could not reproduce here" when nothing was run. Say: "I can only triage here; this still needs to be reproduced."
  (#6450) (R033, X03).

### Weak spots (still the most common misses in model tests)
- **Support vs feature** (#7181, #7048, #7000): run `appcheck` before deciding; if the app does it, it is support.
- **Duplicates**: same command AND same failure, not shared generic words (#7431, #4058); prefer the canonical in
  `duplicate-clusters.md` that has a PR (#6604, #4193). D3 makes a rejected exact-error candidate explicit.
- **Missing design requests**: a modelling failure with no file needs the zip line (Z01).
- **`gui_only` and `has_steps`** are read literally (E1, E7 wording).
- The reporter's own tool had the bug (#7055): G1 answers `no_action`.

### Accounts
- Another account's agent copied the "Verified by dudedagger42" header and posted as if it were that account (upstream
  #5394, #3532, #6260; reported by tbrasselle). Rule: the header is built from the logged-in account and the text may
  hold no signature (S01, R034); `audit` flags any comment whose signature differs from its poster.

## v2
