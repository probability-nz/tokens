# Tokens

Reusable glTF pieces. Authoring files live in each asset's `source` directory;
generated assets live beside them. Asset preparation requires ImageMagick with
AVIF and WebP support.

`src/assets/catalog.json` lists the published pieces.

Assets were created by Misha Tsyatsko under contract for Garbo Succus.

- `pnpm prepare-assets` rebuilds generated assets.
- `pnpm build` validates the catalog and writes `dist`.
- `pnpm dev` builds and starts the catalog preview.
- `pnpm build-storybook` builds the deployable preview.

## Regular dice and face poses

D4 and D12 use centred, mathematically regular meshes with uniform rounded
bevels. Their original numbered artwork and engraved normal maps are rebaked
onto new UVs; blank versions use the identical mesh with the glyphs removed.
Original artwork remains in `source`; the reproducible bake outputs are in
`regular`. Rebuild with Blender 5, Pillow and NumPy available:

```sh
blender -b --python-exit-code 1 --python scripts/assets/regular-dice.py -- d4
blender -b --python-exit-code 1 --python scripts/assets/regular-dice.py -- d12
node scripts/prepare-assets.mjs D4 D12
```

The optional names limit image conversion; omitting them rebuilds all numbered
assets. Preparation also synchronizes blank geometry and generates face metadata.
All blank glTFs share their numbered variant's published `.bin`, including
positions, normals, UVs, tangents and indices. `sync-blank-dice.py` is the single
blank-model generator; only white materials and blank normal maps differ.
D8/D12/D20 outcomes are fitted to the mesh planes and the whole solid's normal
symmetries, preserving the original number mapping and a stable footprint.
`authored-dice-poses.json` retains the original hints for identifying numbered
faces. D4 uses exact tetrahedral rotations. Classic die and D6 poses are unchanged.
Faces are embedded in each glTF as well as the shared catalog, so imported models
retain their roll outcomes without a separate catalog.

```sh
python3 -m unittest discover -s scripts/assets
node scripts/build-catalog.mjs
```

The tests require NumPy, Pillow 11.3+ with AVIF support, and SciPy, and cover all catalog outcomes, stable bounds,
resting planes, regular D4 geometry, and identical numbered/blank model buffers.

## Centered numeral artwork

Preparation measures numerals in their final reading orientation, so rotated UV
islands and 6/9 dots cannot displace the numeral itself. D4's three labels on each
face use identical corner spacing. Lettering uses a common physical height per
die. Digits and disambiguation dots move together with their engraved normal-map
detail; face order, rotations, meshes and UVs are unchanged. Per-die clearance
factors leave room around the tallest/widest labels and their engraving.

`centered/` maps are generated from preserved `source/` or `regular/` maps by
`scripts/assets/center-dice-labels.py`, using NumPy, Pillow and SciPy. Freshly baked
regular blank normals (D4/D12) or original blank normals provide clean surfaces
beneath relocated engravings. Preparation runs this step automatically; repeated
builds never re-center an already processed image.

Tests cover the published AVIFs as well as the PNG masters, physical reading-frame
anchors, equal lettering heights, complete digit/dot components, residual engraving,
and rebuilding regular dice without stale published blank maps.
