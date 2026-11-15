## Failure ID (dry run, v0)

Give every report a failure ID: 5 hex digits (0-9, A-F), `TT MM F`. It goes into the comment's hidden marker only, never into the comment's text. The aim is that two reports of the same bug get the same ID, however differently they are worded. So choose by what failed, not by the reporter's words. If nothing fits, use `F` for that digit and say what was missing in `fail_id_note`.

**TT, the tool:** the first digit is the family, the second is the tool within it.

| Family | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | A | B | C | F |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 app | startup/install | crash, no tool named | preferences/settings | panels/layout | toolbar/menus | keymap | themes/looks | updates | language/translation | | | | | other |
| 1 sketch: draw | line | rectangle | circle/arc | ellipse/conic | spline/fit curve | point | text/glyphs | equation curve | insert DXF/SVG/airfoil | polygon/slot | offset | project/intersect curve | construction | other |
| 2 sketch: edit | constraint | dimension | solve/DOF | trim/extend/break | fillet/chamfer in sketch | mirror/pattern | move/scale/transform | copy/paste | snap/inference | sketch edit/finish/redefine | drag | auto-constrain | delete | other |
| 3 solid: create | extrude | revolve | loft | sweep/pipe | coil/thread | rib/web | emboss | box/cylinder/sphere/cone/torus | hole | boundary fill/bounding solid | press-pull | | | other |
| 4 solid: modify | fillet | chamfer | shell | draft | combine (join/cut/intersect) | split body | split face | delete face/remove | replace/offset face | move/align | mirror | pattern | scale | other |
| 5 surface | extrude/revolve | loft/sweep/ruled | patch/boundary/fill | blend/fillet/match | offset/thicken | trim/untrim | extend | stitch/unstitch | reverse normal | fair | | | | other |
| 6 sheet metal | flange/path flange | fold/refold | unfold/flat pattern | hem | rules | convert | perforate | bend table / DXF export | | | | | | other |
| 7 assembly | components | joints/mates | motion | BOM | mass properties | assembly export | | | | | | | | other |
| 8 drawing | views | dimensions/annotations | export (DXF/SVG/PDF) | sheets/templates | | | | | | | | | | other |
| 9 import/export | STEP import | STEP export | STL/3MF/OBJ | mesh convert | DXF/SVG import | GLB | .sc/.solidcraft open/save | KiCad | | | | | | other |
| A view | navigation/camera | selection/picking | rendering/drawing | section/measure | visibility/hide-show | browser tree | | | | | | | | other |
| B document | timeline/history | undo/redo | parameters/equations | recovery/autosave | parts library | | | | | | | | | other |
| C scripting | MCP/scx | CLI | plugins | Python API | | | | | | | | | | other |

**MM, how it failed:** the first digit is the class, the second is the specific way.

| Class | 0 | 1 | 2 | 3 | 4 | 5 | F |
|---|---|---|---|---|---|---|---|
| 0 stops | crash | hang/freeze | very slow | out of memory | | | other |
| 1 kernel/geometry | refuses with an error | wrong shape (succeeds) | invalid or open body | coincident/tangent faces | self-intersection | tolerance/tiny edges | other |
| 2 interaction | control missing or does nothing | preview differs from result | wrong pick/selection | value/input rejected | layout/draw glitch | | other |
| 3 data | lost on save/load | undo/redo wrong | history replay/regeneration | import reads wrong | export writes wrong | | other |
| 4 graphics | not drawn | artefacts/flicker | GPU/driver | | | | other |
| 5 platform | install/launch | OS-specific | display scaling/DPI | | | | other |
| E | feature request | by design / works as intended | | | | | |
| F | unknown / not enough information | | | | | | |

**F, how specific it is:** 0 = fails on any simple shape; 1 = needs the reporter's design; 2 = needs an imported file (STEP, mesh, DXF); 3 = one OS, GPU or driver only; 4 = one setting or preference only; F = unknown.

Example: a fillet that fails with an error, only on the reporter's design, is `40 10 1` → `40101`. A crash on startup on one GPU is `00 00 3` → `00003`.
