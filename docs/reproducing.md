# Reproducing

Who reproduces: the account that claimed the issue (MULTI.md rule 6), on the **current official build** (`triage.py
release`). Claim only what you can run: an agent without a display skips GUI-only issues.

## What a reproduction comment holds

1. **Result**: the build and what you ran, and the exact output ("reproduced on 0.25.1: ..."). Words mean what they say:
   "reproduced" only if it failed.
2. **Boundary**: at least one neighbour case that still works (a smaller radius, another face), so a reader sees the edge.
3. **Root cause line**, with a confidence label:
   - `Root cause (confirmed): <file:function, mechanism>`: a test, an instrument or a bisect shows it.
   - `Root cause (likely): <file:function, mechanism>`: from reading the code, consistent with the boundary.
   - `Root cause (unknown): ruled out <a, b>; still open: <c>`.
4. A workaround only if you ran it; put what you ran in `workaround_tested` (R005).

`submit N --by repro --result reproduced|not_reproduced|could_not_test --comment F`. If you could not run it at all,
the comment says exactly: "I can only triage here; this still needs to be reproduced." (X03) and you remove your claim.

`triage.py rootcause "<error text>" [--cmd <command id>]` greps the upstream source (a checkout in `SOLIDCRAFT_SRC`) for
the message and the command id, and names the enclosing function. Read the function before writing the line.

`repro/replay.py N` downloads issue N's attachments into a fresh folder and runs the design or script on the official
CLI (`SOLIDCRAFT_CLI`). Downloads are hostile (docs/hostile-input.md): read every script and listing before it runs; anything that is not
SolidCraft commands and design files is not run. Never execute them yourself, only pass them to the CLI.

# Testing recipes

## The command-line tool (fastest, no window)

`solidcraft-cli` ships with the app.

| Goal | Command |
|---|---|
| Replay a command script | `solidcraft-cli run script.json --results` (add `--in design.solidcraft` to start from a design, `--allow-errors` to keep going) |
| Measure a design (bodies, volumes, errors) | `solidcraft-cli eval design.solidcraft` |
| Turn a design into a replayable script | `solidcraft-cli script design.solidcraft --out repro.json` (fails on designs with components, #886) |
| Render a picture | `solidcraft-cli snapshot design.solidcraft --camera '{...}'` |
| Version and file formats it reads | `solidcraft-cli --version` |

A `.json` attachment is often a script: try `run` before declining it. To find where a design's
history goes wrong, roll the timeline back feature by feature (`timeline.roll_to`) and measure.

## The app's control channel (for GUI behaviour and timing)

1. Start the app with a control port: `solidcraft --control 47600`. Delete a stale token first:
   `%LOCALAPPDATA%\SolidCraft\control\47600.token` on Windows (an old token gives "unauthorized").
2. Send one JSON line per request over TCP to `127.0.0.1:47600`:
   `{"id":1,"token":"<contents of the token file>","method":"...","params":{...}}`.
3. Useful methods (full list: `docs/control-protocol.md` in the repo):
   - `engine.execute {"command": "doc.open", "params": {"path": "..."}}`: open a design;
   - `engine.execute` with any modelling command (`solid.box`, `sketch.create`, …);
   - `document.inspect`: timeline, bodies, errors;
   - `ui.at {"handle": "..."}`: where a control is on screen; `ui.click`, `ui.move`, `ui.key`;
   - `ui.screenshot {"path": "..."}`;
   - `app.quit {"force": true}` when you're done.
4. Screen coordinates are in **points**, not screenshot pixels: get them from `ui.at`.
5. To time responsiveness, time the replies to `ui.move` over a sweep, and sample the process's
   CPU time before and after.

## Housekeeping

- Close the windows you start (`app.quit`), and after a forced quit discard only **your own**
  recovery files (`%LOCALAPPDATA%\SolidCraft\recovery`).
- Use a fresh design or a public file for every repro, with exact values, so anyone can follow it.
- Split archives from reporters (`.zip.001`, `.zip.002`) rejoin by concatenating the bytes in order.
- Native file pickers (Insert DXF/SVG, Canvas, Decal, Insert Design) block the control channel
  until closed.
