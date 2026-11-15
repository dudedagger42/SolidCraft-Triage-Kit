## Failure ID (v1)

Give every report a failure ID: 11 hex digits (0-9, A-F, uppercase), `TT MM K SSSSSS`, written without spaces. It goes into the comment's hidden marker only, never into the comment's text:

`<!-- sc-fail-id v1 40103A1C4F8 -->`

| Part | Digits | What it is | Who decides |
|---|---|---|---|
| `TT` | 1-2 | the tool that failed | you, from the tables below |
| `MM` | 3-4 | how it failed | you, from the tables below |
| `K` | 5 | what kind of error text the report holds | `failid.py` |
| `SSSSSS` | 6-11 | signature of the program's own error message | `failid.py` |

**What an equal ID means.** Compare the last 7 digits (`K SSSSSS`), not the whole ID. `TT` and `MM` describe the report; the same bug is reported from different tools (the Shell and Offset Face reports of #2432 differ in `TT` and share the signature).

| K | The report holds | Two reports with the same `K SSSSSS` are |
|---|---|---|
| 1 | a refusal of the input or the state ("there is no body to cut or intersect") | the same bug. Link as duplicates. |
| 2 | a limit or other refusal ("not supported yet: ...") | the same refusal. Duplicates, unless one of them shows the refusal itself is wrong (the limit quoted is far below what the faces allow, say). |
| 3 | a failure inside the kernel ("SMLib ... (status 1001)", "SMLib's check refuses the result", "solidcore: ...", "boolean Cut: ... no result") | the same failure class only. Never a duplicate on the ID alone: compare the files. |
| 0 | no error text (`SSSSSS` = `000000`) | nothing. The ID is a bucket for counting. |
| F | an error the report mentions without giving its words, or a message `failid.py` cannot key (`SSSSSS` = `000000`) | nothing. |

A wrong shared ID is worse than a missed one. When a rule below says F, use F.

### Step 1: the error text

Go down the list and stop at the first that applies.

1. The section `## Operation context` holds a message in double quotes: that message. ("No command error was recorded." is not a message; go on.)
2. The section `## Actual behavior` begins with a message in double quotes: that message.
3. Elsewhere in the title or body the reporter gives the program's own message: in quotes, in a code block, after "error:", "message:" or "says", or a sentence that starts like the program's messages ("not supported yet:", "invalid input:", "invalid parameters for", "SMLib ...", "body `...`: the operation failed"). Take the first one.
4. The reporter says the step failed, was refused or gave an error, but the words are not in the report (only in a screenshot, or the title is "TOOL: operation failed" with no message): the error is **mentioned**. `K` = F.
5. Otherwise there is **none**. `K` = 0.

Copy the message character for character, whole, without the outer quotes. Do not translate, correct or shorten it.

Never the message:

- any line of the log under `Messages (last ...`, also its `error:` lines. They are old events, mostly unrelated to the report.
- lines under `Failing features`.
- labels, hints or tooltips of the interface that the reporter quotes while describing a screen.
- the sentence "A failed preview may display the last valid geometry...", the title "TOOL: operation failed", template words ("Not provided").
- the reporter's own description, and anything you found yourself by replaying the file. The ID is made from the report as filed, so that a back-fill and a live triage give the same ID. Put a message from your own replay in `fail_id_note`.

### Step 2: TT, the tool

The first digit is the family, the second is the tool within it.

| Family | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B | C | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 app | startup/install | crash, no tool named | preferences/settings | panels/layout/windows | toolbar/menus | keymap/shortcuts/mouse buttons | themes/looks of the interface | updates | language/translation | | | | | other |
| 1 sketch: draw | line | rectangle | circle/arc | ellipse/conic | spline/fit curve | point | text | equation curve | insert DXF/SVG/airfoil/image | polygon/slot | offset | project/intersect curve | construction | other |
| 2 sketch: edit | constraint | dimension | solve/DOF | trim/extend/break | sketch fillet/chamfer | sketch mirror/pattern | move/rotate/scale/transform | copy/paste | snap/inference | create/edit/finish/redefine a sketch (its face or plane) | drag | auto-constrain | delete | other |
| 3 solid: create | extrude | revolve | loft | sweep/pipe | coil/thread | rib/web | emboss | box/cylinder/sphere/cone/torus | hole | boundary fill | press-pull | construction plane/axis/point/coordinate system | | other |
| 4 solid: modify | fillet | chamfer | shell | draft | combine/boolean | split body | split face | delete face/remove | replace/offset face | move/align/copy body | mirror | pattern | scale | other |
| 5 surface | extrude/revolve | loft/sweep/ruled | patch/boundary/fill | blend/fillet/match | offset/thicken | trim/untrim/split | extend | stitch/unstitch | reverse normal | fair | | | | other |
| 6 sheet metal | flange | fold/refold | unfold/flat pattern | hem | rules (thickness, bend radius, K factor) | convert | perforate | bend table / DXF export | | | | | | other |
| 7 assembly | components | joints/mates | motion | BOM | mass properties | assembly export | | | | | | | | other |
| 8 drawing | views | dimensions/annotations | export | sheets/templates | | | | | | | | | | other |
| 9 import/export | STEP import | STEP export | STL/3MF/OBJ | mesh convert | DXF/SVG import | GLB | .sc/.solidcraft open/save | KiCad | | | | | | other format |
| A view | navigation/camera/mouse control | selection/picking | rendering/shading/colours of the model | section/measure | visibility/hide-show | browser tree | | | | | | | | other |
| B document | timeline/history | undo/redo | parameters/equations | recovery/autosave | parts library | configurations | | | | | | | | other |
| C scripting | MCP/scx | CLI | plugins | Python API | | | | | | | | | | other |

First rule that applies:

1. `## Settings and selection` holds a command id (`"solid.fillet"`, `"sketch.fillet"`, `"construct.plane.offset"`; inside `"timeline.redefine"` use its `"command"`): that command. `sketch.*` is family 1 or 2, `solid.*` 3 or 4, `surface.*` 5, `construct.*` 3B, `sketch.create` 29.
2. The title starts with a tool in capitals ("SHELL: operation failed"): that tool. FILLET or CHAMFER whose message speaks of corner points or sketch lines is 24. MIRROR whose message speaks of a mirror line or a sketch is 25. SURFACE LOFT is 51, CREATE SKETCH 29, OFFSET PLANE 3B, CONVERT MESH 93, CIRCULAR PATTERN 4B. "Part:" names no tool.
3. The program does not start, install or update: 00 (07 for the updater). Otherwise the tool whose step failed or gave the wrong result: the last step before the failure. Not the tools that built the model earlier, and not where the data came from (a fillet that fails on an imported STL is 40, not 92).
4. Two tools fit equally: the one the title names first. Family known, tool not listed: `xF`. Family not clear: `FF`.

### Step 3: MM, how it failed

| Class | 0 | 1 | 2 | 3 | 4 | F |
|---|---|---|---|---|---|---|
| 0 stops | crash | hang/freeze | very slow | out of memory | | other |
| 1 kernel/geometry | refused with an error | wrong shape, no error | open, broken or invalid body | | | other |
| 2 interaction | control missing or does nothing | preview differs from result | cannot pick / wrong pick | value or input rejected | layout or draw glitch | other |
| 3 data | lost or changed on save and reopen | undo/redo wrong | features fail or change after an earlier edit | import reads wrong | export writes wrong | other |
| 4 graphics | not drawn | artefacts, flicker, wrong colours, brightness or shading | one GPU or driver | | | other |
| 5 platform | install/update/launch | | display scaling/DPI | | | other |
| E not a defect | new tool, option, mode or format | by design (triager's call after checking; never from the report alone) | change how something that exists looks, behaves or defaults | question, how-to | | |
| F | unknown (`FF`) | | | | | |

First rule that applies:

1. The report asks for something and reports no defect: `E2` when it asks to change something that already exists (make it scroll, less bright, customisable, a different default); `E0` when it asks for something that does not exist yet. Both or unsure: `E0`.
2. Only a question on how to do something: `E3`.
3. The program closes, crashes or panics: `00`. Freezes: `01`. Works but very slow: `02`. Out of memory: `03`.
4. Install, update or launch fails: `50`.
5. An error is quoted or mentioned (step 1): `10` when `TT` is in family 3, 4, 5, 6 or is 93; otherwise `23`.
6. On screen only, the model itself is right: `40`, `41` or `42`. Only display scaling: `52`.
7. Content of the file gone or different after save and reopen: `30`. Undo/redo: `31`. Features fail or change after editing an earlier step or parameter: `32`. Import: `33`. Export: `34`. A file from an older version whose step now fails is not `30`; note the regression and go on.
8. The operation finishes without a message and the geometry is wrong: `11`. The body is open, broken or invalid: `12`.
9. `20`, `21`, `22`, `23` or `24` from the table.
10. None of these: `FF`.

### Step 4: K and SSSSSS

Do not make these digits. Give the kit your part in the answers as `fail`:

```
"fail": {"tt": "40", "mm": "10", "error": "quoted", "error_text": "SMLib fillet: operation: the blend failed (status 1001): the fillet body is not built: Fillet Surface Computation Failure"}
```

`error` is `quoted` (rules 1-3 of Step 1), `mentioned` (rule 4) or `none` (rule 5). The kit checks that `error_text` is in the report word for word (if not, it counts as `mentioned`), makes the ID with `kit/failid.py` and stores it as `fail_id`, with the hashed key as `fail_key`. To see an ID by hand: `python kit/failid.py code 40 10 "<message>"`.

What the script does, so the result can be checked by eye:

- lower case; body and feature names in backticks, numbers, coordinates and file paths are dropped (the numbers in "status 1001" and "Test #5" stay);
- wrappers in front are dropped ("body `X`: the operation failed:", "invalid parameters for `cmd`:", "invalid input:", "not supported yet:", a one- or two-word tool or feature name);
- a refusal is keyed on its first two clauses, so "the fillet is larger than the faces beside its edges allow; no smaller radius builds either" and "...; the largest radius that fits is 0.07 mm" get different signatures: they have turned out to be different bugs;
- "SMLib's check refuses the result" is keyed on the kernel stage and the first failed test ("check boolean SmFace Test #36 face near missing seam");
- other kernel failures are keyed on the whole first line up to the first semicolon;
- `K` = 3 for kernel text (starts with "SMLib", holds "solidcore", "::", "(status N)") and for the messages in the script's `GENERIC` list; `K` = 1 for "invalid input" / "invalid parameters" refusals and the messages in its `STRONG` list; `K` = 2 for every other refusal;
- a message of fewer than three words, or with no Latin letters left (a translated interface), gives `K` = F.

### Upkeep (coordinator)

Three lists at the top of `failid.py` carry what the hashing cannot know. Each change alters IDs, so log it like any rule change.

- `ALIASES`: old wording of a message → the key of today's wording, when a message was reworded between versions.
- `STRONG`: refusals confirmed to be one bug each. Seeded from `duplicate-clusters.md`.
- `GENERIC`: messages found on unrelated geometry ("no result", "the blend is larger than the neighbouring faces", "the cut could not be computed reliably"). Add a message here as soon as two reports with the same `K` 1 or 2 signature turn out to be different bugs.

### Examples

| Report | ID | Reads as |
|---|---|---|
| CREATE SKETCH, "Create Sketch: this face can't keep an attachment: its history can't tell it apart ..." | `2923112E046` | sketch create, input rejected, refusal `12E046` |
| OFFSET PLANE, "invalid parameters for `construct.plane.offset`: this face can't keep an attachment: ..." | `3B10112E046` | other tool, same `112E046`: duplicate of the row above |
| FILLET, "SMLib fillet: operation: the blend failed (status 1001): ... Fillet Surface Computation Failure" | `40103A1C4F8` | fillet refused, kernel failure class `A1C4F8` |
| "Shell not working ... it fails with an error", message only in a screenshot | `4210F000000` | shell refused, message not given: matches nothing |
| "Making the ribbon menu scrollable" | `04E20000000` | toolbar, change to something that exists |
