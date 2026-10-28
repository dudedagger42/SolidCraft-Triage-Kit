# Known duplicate clusters

Reports that quote **the same specific error** as a canonical issue. Use this as a starting point only: check the live state of the canonical issue and its PR before you link it, and confirm the new report's error text really matches. Generic failures ("boolean Union/Cut: no result", blend refusals) were deliberately **not** grouped, because the same words cover different geometry.

Live state checked 2026-10-24.

| Canonical | Error | Live state | Known duplicates |
|---|---|---|---|
| #4325 | "this face can't keep an attachment" (Create Sketch, Offset Plane) | open; draft PR #3914 covers one variant | #1874, #1878, #2097, #2111, #2125, #2380, #2478, #2493, #2505, #2514, #2530, #2585, #2722, #3037, #3109, #3438, #3530, #3603, #3621, #3723, #4078, #4135, #4259, #4395, #4509, #4578, #4584, #4612, #4805 (29) |
| #2432 | "offset: only bodies with planes, cylinders, cones, spheres and tori" (Shell, Offset Face) | open; kernel limit | #1525, #2239, #2480, #2659, #2886, #2905, #2917, #3000, #3105, #3346, #3721, #4279, #4306, #4503 (14) |
| #4639 | "there is no body to cut or intersect" | open; PR #4641 open | #1231, #2055, #2370, #3090, #3112, #3138, #3406, #3498, #3808, #4355, #4413, #4424 (12) |
| #3038 | "a boolean needs a solid body; mesh bodies can only be…" | open; by design (Convert Mesh first) | #1965, #2543, #3251, #3374, #3496, #4523 (6) |
| #4193 | "The mirror line must be a straight curve of this sketch, not an origin axis" | open, in progress; PR #4207 open | #3632, #4042, #4077, #4240, #4865 (5) |
| #4506 | "unknown sketch line" (Revolve about a construction axis) | closed; PR #4511 closed | #2516, #3619, #4576, #4738 (4) |
| #4732 | "the selected planar face no longer exists" | open | #521, #943, #2351, #3470, #3484, #4648 (6) |
| #4555 | "select at least one face to remove" (Shell) | open; kernel | #3074, #4120, #4573 (3) |
| #2987 | "there is no sheet metal body" | closed; PR #4789 merged | #3502, #4161, #4514 (3) |
| #2885 | "axis must be X, Y, Z or {origin, dir}" (Circular Pattern) | closed; PR #3796 merged | #3811, #4741 (2) |
| #4609 | "activate the mesh body's component before converting it" | closed; PR #4613 merged | #3942, #4814 (2) |
| #358 | "mesh conversion: this mesh is not a supported constant-section prism" | open; mesh conversion | #1200, #2235, #4564, #4586, #4632 (5) |
| #346 | "mesh exceeds the conversion budget" / "more than the 50 000 triangles" | open; by design (triangle cap) | #4560 (1) |
