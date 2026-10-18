# Blank original dice

Blank variants of the actual `probability-nz/tokens` catalog models used by
Play's Create tab: D4, D6, D8, D12 and D20. No new shapes are generated.

Mesh buffers (including positions, vertex normals, UVs and indices), nodes,
accessors, dimensions, samplers and material roughness are preserved exactly.
The white base colour replaces the printed-number texture. The edited normal
map flattens only the engraved numerals/pips, retaining the original bevels.
UVs are deliberately retained because those bevels are baked into the same map.
Each glTF embeds its original binary buffer and references its adjacent PNG.
Keep both files together when importing.

Source: https://github.com/probability-nz/tokens
Source commit: b2559ef (same asset tree as probability/main b49bad1).
CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
Garbo Succus; source assets by Misha Tsyatsko.
Modified: number/pip albedo removed, normal-map numeral/pip regions flattened.
Original geometry and bevel map regions are unchanged.

## Editing and validation

`python3 scripts/assets/blank-dice.py /path/to/tokens` regenerates from original
lossless source maps. Requires Pillow, NumPy and SciPy; defaults to this repository.
The masks find enclosed dark numeral/pip regions in the albedo and expand to
include their engraved lips, then harmonically interpolates the surrounding
normal field across those regions. No image synthesis or new mesh generation is used.
For manual changes, edit the normal PNG in an image editor, leaving bevels intact.

`python3 -m unittest discover -s scripts/assets` verifies byte-for-byte geometry
preservation against the original assets in this repository and preservation of material settings.

Run `pnpm dev` and open Assets / Blank Dice / Full Set in Storybook.
The model-only WebGL preview loads the real glTF materials and normal maps.
Drag any model to orbit all five together; scroll over any model to zoom all five.
The catalog appends blank variants after all existing pieces, retaining their
original scale, rotation and outcome metadata.
