# Blank dice

D4, D6, D8, D10, D12 and D20 blanks use the exact same rounded geometry, UVs,
normals, tangents, dimensions and face poses as their numbered counterparts.
Each glTF references its numbered model's published mesh buffer. Classic and
D6 also share one buffer. No blank model embeds a duplicate mesh.

All blanks use white base colour and one shared neutral normal-map texel.
The 1.2 mm rounded edges and corners come from geometry and smooth normals;
there is no numbered engraving or old bevel shading in the blank material.

Keep the catalog directory layout when copying assets, or use the app export
to bundle dependencies. Each numbered die's `paint/` directory contains PNG
painting layers and guides usable with either version of the same die.

Run `node scripts/prepare-assets.mjs` to prepare numbered assets, synchronize
blank geometry, embed face metadata, and regenerate painting templates.
`sync-blank-dice.py` is the single blank-model generator; `blank-dice.py` is its
compatibility entry point. The full process is documented in the root README.

Run `python3 -m unittest discover -s scripts/assets` to verify shared buffers,
material settings, rounding, UVs and all face poses. Run `pnpm dev` for the
Storybook preview, including Assets / Blank Dice / Full Set.

Source: https://github.com/probability-nz/tokens
CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
Garbo Succus; original source artwork by Misha Tsyatsko. D10 artwork is generated.
