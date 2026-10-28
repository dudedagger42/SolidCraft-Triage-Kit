# Lints

Every comment is checked before `post`, `fix` and `reply`. A **block** stops the post; a **warn** is shown to the reviewer.
Profiles: `first` (the first pass, which runs nothing), `repro` (ran it), `all`.

## Code lints (`kit/triage.py`, `lint_comment`)

| Id | Severity | What |
|---|---|---|
| S01 | block | A signature ('Triage by', 'Verified by') in the text: the kit adds the one header from the posting login |
| Q01 | block | More than one question (reproductions excepted) |
| T01/T02 | block | A postable verdict without a comment, or a comment on needs_repro / no_action |
| T03 | block | Over the length limit (first pass 900, reproduction 2400, reply 900) |
| G01 | block | Doubled word: a garbled edit |
| G02 | block | Unbalanced backticks, bold markers or parentheses |
| G03 | block | Does not end with a full sentence |
| G04 | warn | A sentence starts in lower case |
| V01 | block | Asks to retest on a version that is not the current release (live from gh release list) |
| P01 | block | A local path with a user or folder name |
| P02 | block | A name from state/private-names.txt (private or work files) |
| P03 | warn | Links an upload: make sure it is a public test file |
| M01 | block | @-mentions anyone but the reporter |
| M02 | block | Asks for a screenshot or recording when the thread already has one |
| N01 | warn | Links an issue that is not in the case, the thread or the answers |
| K01 | block | Kernel framing (#3992, 'kernel work') when E9 says the step is not in the kernel |
| Z01 | block | Modelling failure with no file, and no zip request |
| Z02 | block | Zip request on a crash, GUI or usage report |
| D02/D05 | block | Duplicate comment does not link the issue, or does not say it is closed |
| X01 | block | Reproduction without a Root cause (confirmed|likely|unknown) line |
| X02 | block | Reproduction or non-reproduction without the build it ran on |
| X03 | block | could_not_test without the exact 'I can only triage here; this still needs to be reproduced.' |
| L01 | block | Non-English report without the translation |
| L03 | block | A follow-up reply to someone who did not write English, without `reply --translation F --language L` |

## Answer checks (`validate`, before `decide`)

Every applicable checklist question answered with the right type; `app_check` for how-to and feature questions; a real reason in `attachment_not_runnable` (never 'cannot download'); `duplicate_of` only from the candidates or the cluster table, with the shared text; an exact-error candidate rejected with a reason.

## Pattern lints (`kit/rules.json`)

| Id | Profile | Severity | What |
|---|---|---|---|
| R001 | all | block | Speaks for the project ('we ...'). Report facts; maintainers decide. |
| R002 | all | block | Thanks or filler. Every comment must move the issue forward. |
| R003 | first | block | The first pass runs nothing: a bug with steps or a file is needs_repro. |
| R004 | first | block | Claims an action the first pass does not perform. |
| R005 | all | block | Untested workaround. A workaround is allowed only from the repro profile with `workaround_tested` filled in. |
| R006 | all | block | Praises the report or an attachment. |
| R007 | all | block | Speaks for the maintainers or promises work. |
| R008 | all | block | 'Can't download' excuse: zip and tar both extract with the kit (repro/replay.py). Run it, or say exactly what the archive holds. |
| R009 | all | block | Mentions a .solidcraft file without telling the reporter to zip it (GitHub refuses a bare .solidcraft). |
| R010 | all | warn | 'Fixed in <version>' needs the fix's merge time checked against the release time, in source. |
| R011 | all | block | Asks for a file that is already attached in the thread. |
| R013 | all | block | Template fragment or placeholder left in the text. Re-read the whole comment as the reporter will. |
| R014 | all | warn | Filler or condescension. |
| R015 | all | block | Describes what a screenshot shows without having opened it. Open it (image_files) and list it in images_viewed, or say nothing about it. |
| R016 | all | block | Internal tooling named in a public comment. Say 'I found no existing request', not 'the case file shows'. |
| R017 | all | block | Restates the report. Start with the question or the answer. |
| R018 | all | block | 'The command list' is tooling, and cannot answer questions about buttons, options or settings. Say what you saw in the app, or that you did not check it. |
| R019 | all | block | View modes and visual styles are UI, not commands. Check docs/ui-features.md and the view toolbar first. |
| R020 | all | block | Translation written inside the comment. Put it in the `translation` field only (the kit appends it). |
| R022 | all | block | The Environment block already gives the version; ask only for what is missing. |
| R023 | all | block | The Environment block's Renderer line names the GPU; read it before asking. |
| R024 | all | block | Do not ask whether a split-off request should stay under its parent: link the parent and ask a real product question, or post nothing. |
| R025 | all | block | The Environment block already gives the OS. |
| R026 | all | block | A triager cannot file, log or track anything. Say what the app does or ask the question. |
| R027 | all | block | A kernel comment needs one pointed question or the zip line; 'kernel work is paused (#3992)' alone adds nothing. |
| R029 | all | block | Generic request for 'more information'. Ask for ONE named thing (the design zipped, the error text, the step that fails). |
| R030 | all | block | Priority and importance are internal. Labels and ranking belong to the maintainers. |
| R031 | all | block | Talks about itself instead of the issue. The header already says who posted. |
| R032 | all | block | Markdown heading in a comment. Plain sentences; a reproduction may use bold labels. |
| R033 | all | block | When you could not run it, say exactly: 'I can only triage here; this still needs to be reproduced.' |
| R034 | all | block | A signature line inside the text. The kit adds the one header ('Triage by <account>'); never write another. |
| R035 | all | block | Instructs the reporter as if a fix were known. Ask whether it still happens on the current release instead. |
| R036 | all | warn | A cause stated from a guess. Name the evidence (the error text, the file:function you read) or ask a pointed question. |
| R037 | all | block | 'Same as #N' is a duplicate claim. Use the duplicate verdict (same command AND same failure, live-checked), or say 'related: #N' and why. |
| R038 | all | warn | Emoji in a triage comment. |
| R039 | repro | block | A reproduction must name the build it ran on ('reproduced on 0.25.1'). |
