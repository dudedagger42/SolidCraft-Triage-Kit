# Good results

Comments that did what the kit is for. Read these next to `lessons.md`: lessons show what went wrong, these show what
right looks like.

## #8306: the maintainer wrote his own PR from the triage (2026-10-28)

https://github.com/tangency-labs/solidcraft/issues/8306. Dahak's agent, kit v2.13.

The reporter, a SolidCraft developer, first said his issues did not need triage. The comment:

- confirmed the current state on the official 0.25.1 build and on main at a named commit;
- showed the command's real parameters, and that the one the request needs is silently ignored;
- named the two places in the document format that stop it (`crates/doc/src/document.rs`, `crates/doc/src/joints.rs`).

He then claimed the issue and opened his own PR (#8316).

**Why it worked:** every claim was checked in the source or on the build, with file and line, so a developer could act
on it without redoing the search.

## #8322: duplicate and root cause in one comment (2026-10-28)

https://github.com/tangency-labs/solidcraft/issues/8322. Same agent, kit v2.13.

- Found the earlier request (#2112) and the open PR that addresses it (#2222), with the same gesture and the same
  modifiers. Duplicates need the same command and the same failure.
- Confirmed the report's diagnosis in source at a named upstream commit: `immediate_wheel` in
  `crates/ui-egui/src/navigation.rs` drops wheel events that carry egui's zoom modifier.
