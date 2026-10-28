# UI features that are not commands (so `solidcraft-cli commands` does not list them)

`triage.py appcheck "<keyword>"` searches the command list AND this file. Seen in 0.20-0.23 on Windows.
Add a line when you confirm one; say where it is and how to reach it.

- **Search commands** (command palette): top-right box in the window, shortcut **S**. Typing finds commands by name.
- **Toolbar tabs:** Model, Surface, Assemble, Insert, Inspect, Manage, View, Sheet Metal (the workspace button at the left switches workspaces, e.g. Design).
- **Browser** (left): Document Settings, Named Views, Origin, Bodies, Sketches, Construction, Features. Eye icons show/hide; right-click for item actions.
- **History bar** (bottom): the timeline of features as icons, with roll back / forward buttons.
- **Parameters** button (Model tab, Configure group), **Config Table**, **Move / Copy** (Arrange group), **Press Pull** (Q), **Offset Plane** (Construct).
- **View cube / axis gizmo** (top right) with a Home button; a small view toolbar at the bottom of the viewport (orbit, pan, zoom, fit, look at, view modes).
- **Preferences** (gear, top right): General, Interface, Design, Navigation, Shortcuts, Sketch & selection, Graphics, Assistant, Plugins. Design has Units, Length/Angle decimals and Orientation (Z up default, Y up); Navigation has navigation presets and "Ring of tools on the right button" (mouse gestures, Customize...).
- **Report a bug** button (top bar): fills an in-app report; **Update to ...** button when a newer release exists.
- **Sketch Palette:** toggles for Snap, Grid, projected, construction, dimensions, constraints (snap lattice depends on zoom; see #7114).
- **Ground shadow, Anti-aliasing, graphics backend** live under Preferences > Graphics.
- **View toolbar "Visual style" button** (bottom of viewport) and Preferences > Graphics > Visual style: Shaded with edges, Shaded, Wireframe, Shaded with hidden edges. Not a command, so the command list has no "wireframe".
- **Selection filter and Select Other:** a filter decides which kinds (body/face/edge...) a click picks; holding a click still opens Select Other, a list of everything under the cursor (seen in source, 0.23-era checkout; not clicked).
