# Verify pass (run in a FRESH context, never in the turn that wrote the comment)

Input: the case (`state/cases/N.json`), the answers, and the queued comment (`state/queue/N.json`, `final_comment`).
Output: one line, `VERIFY #N ok` or `VERIFY #N fix: <check number, what to change>`. Answer each check yes/no from the
text in front of you, not from memory. `post --approve` on a REVIEW item needs this pass to say ok.

1. **Environment.** Does the comment ask for a version, OS, graphics card or driver that the case's `environment` or the
   body already gives? (Then fix.)
2. **Existence claims.** Does it say a feature exists, is missing, or "can already be done"? Was it confirmed by
   `appcheck` and `docs/ui-features.md`? A command list cannot prove a UI feature absent.
3. **Duplicate.** Does the linked issue match the SYMPTOM and the AREA (same command, same error, same visible failure),
   not just a generic error ("operation failed", "boolean Union: no result")? Is its live state what the comment says?
4. **Restating.** Does the comment repeat the report or the bot? (Start with the question or the answer.)
5. **Already given.** Does it ask for something already attached or answered in a comment?
6. **Zip.** Does it ask for a design? Only for a modelling failure where the design matters, always zipped, never for a
   crash, GUI or usage report, never when a file is attached. A kernel assertion in a "Crash:" report is a crash.
7. **Claims.** Does it say "reproduced", "I confirmed", "workaround", "fixed in", "we will", "thanks", or promise
   anything for the maintainers? Only a run on the current release may say what was run, and what was and was not tested.
8. **Kernel.** Kernel area while #3992's pause lasts: describe only, no workaround, plus one question or the zip line.
9. **Privacy.** No private or work file, no local path, nothing from `state/private-names.txt`.
10. **Thread state.** Is the issue closed, labelled `kernel-paused` / `in progress` / `claimed`, linked to a PR, or did a
    person (or another triage account) comment after the case was built? (Then do not post; rebuild the case.)
11. **One question.** One specific question or none. No template question, no "more details".
12. **Wording.** Plain, short, no jargon the reporter did not use, no fragments left from an edit, the reporter's
    language as a second paragraph when they did not write English.
13. **Index numbers.** Profile, sketch, body and face numbers match the saved command and say their base. `profiles: [0]`
    is "profile 0" (0-based), never "profile 1".
14. **Capability limits** ("limited to", "only works on") match the command's source, not only its list entry. (#7727:
    Emboss was wrongly called planar-only; `crates/kernel/src/emboss.rs` also handles a tangent exterior cylinder.)
15. **Cited issues.** A linked issue cited for the same symptom, card, setting or area really says that: open it. (#7822
    cited #6948 for a corruption "at a Quality setting"; #6948 names no Quality setting.)
16. **Panel and menu claims** ("only toggles", "has no option for") match the option list in source. (#7861: the Sketch
    Palette has ten options, built in `crates/engine/src/cmd/sketch.rs` `options_json`, not one.)
17. **"Nothing does X" claims** hold for every command family that could do it, `construct.*` included. (#7832: the
    `construct.point.*` commands make standalone points.)
18. **Kernel framing** only when the failing step runs in the kernel: a kernel error, or code under `crates/kernel`. An
    `area:kernel` label is not enough. (#7177: Point to Point move is computed in the Move dialog.)
19. **"Not something SolidCraft controls"** only after checking SolidCraft's own preferences
    (`crates/ui-egui/src/prefs/*.rs`, labels in `assets/locales/en.json`). (#7965: Preferences has a slicer-reuse option.)
20. **Quoted project rules** say what the document says (CONTRIBUTING.md, docs/), not what someone said it says. (#7967)
21. **Retest version** is the current release from `gh release list -R tangency-labs/solidcraft -L 1` (lint V01).
22. **Crash records**: what a record holds (a replay or not, which commands) is read from THIS report's own sections, not
    copied from a similar report. (#6830 copied #6839.)
23. **Preview vs OK**: a hang that the live preview did not have is not in the kernel step the preview already ran; the
    preview runs the same commands as OK (`crates/ui-egui/src/dialogs.rs` `preview_commands`). (#8028)
24. **Sibling already asked**: the same failing step asked about on a sibling issue gets a pointer to it, not a second
    request. (#6699 and #6690)
25. **Signature.** The comment holds no "Triage by", "Verified by" or other signature line: the kit adds the one header,
    as the posting account (lint S01). (Another account copied a dudedagger42 header on #5394, #3532 and #6260.)
26. **Claim (MULTI).** You hold the claim (`claim N` said so), and no other account has a triage comment on the thread.

Any "fix": change the answers or the comment, `submit` again, re-run this pass once. Two failed rounds: do not post; write
the reason in `notes` and leave it for review.
