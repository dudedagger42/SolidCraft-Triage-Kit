# Importance and priority

## Importance, 1 to 10 (checklist I1)

Think of everyone who uses SolidCraft. How many would hit this, and how often?

| Score | Band | Meaning | Example |
|---|---|---|---|
| 1-2 | one person | A very niche case; one odd setup | One design with a rare feature combination; a driver bug on one old card |
| 3-4 | few | A narrow group: one OS version, one GPU family, one rarely used command | A command that fails for tapered pockets above a size |
| 5-6 | some | A real group or a moderately used command | One tool's dialog misbehaves in a common but not daily flow |
| 7-8 | many | A common command or setup; most users hit it within weeks | Sketch on a face attaches to the wrong face |
| 9-10 | everyone | The everyday path: open, save, sketch, extrude, view, first run; or data loss | A startup crash on a common GPU |

Crash or data loss on a common path is at least 8. An exotic setup is at most 4. I2 names who and how often.

## Priority (computed by `route`, never guessed)

| Priority | When |
|---|---|
| P0 | Crash or data loss with importance 8 or more, or the maintainers flag it as blocking (`submit --p0 "reason"`) |
| P1 | Bug, importance 8-10 |
| P2 | Bug 5-7; enhancement or support 7-10 |
| P3 | Everything else |

Priority is internal: your queue and your report. It is never posted (R030). Labels and ranking belong to the maintainers.
