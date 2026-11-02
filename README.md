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

All six dice shapes (including the classic pip cube) use centred, mathematically
regular meshes with a **0.6 mm geometric fillet radius at catalog scale**. Faces
are flat; edges are cylindrical and corners spherical, with six subdivisions
per arc. Original artwork is transferred onto the new UVs; engraving is rebuilt
from the final ink. Blank versions share the exact same mesh.

Original artwork remains in `source`; reproducible bake outputs are in `regular`.
Rebuild with Blender 5, Pillow and NumPy available:

```sh
for die in die d4 d6 d8 d12 d20; do
  blender -b --python-exit-code 1 --python scripts/assets/regular-dice.py -- "$die"
done
node scripts/prepare-assets.mjs
```

The optional names limit image conversion; omitting them rebuilds all numbered
assets. Preparation also synchronizes blank geometry and generates face metadata.
All blank glTFs share their numbered variant's published `.bin`, including
positions, normals, UVs, tangents and indices. `sync-blank-dice.py` is the single
blank-model generator; all blanks share one neutral normal-map texel.
`blank-dice.py` is a compatibility entry point for this same generator.
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
resting planes, regular geometry, the shared physical fillet radius, and identical
numbered/blank model buffers.

## Centered numeral artwork

Preparation measures numerals in their final reading orientation, so rotated UV
islands and 6/9 dots cannot displace the numeral itself. D4's three labels on each
face use identical corner spacing. Lettering uses a common physical height per
die. Digits and disambiguation dots move together. Engraved normal-map detail is
regenerated from the final ink so old print/engraving offsets cannot survive.
Face order, rotations, meshes and UV coordinates are unchanged. Per-die clearance
factors leave room around the tallest/widest labels and their engraving.

`centered/` maps are generated from the `regular/` bake by
`scripts/assets/center-dice-labels.py`, using NumPy, Pillow and SciPy. All dice
use analytic mesh normals with neutral blank maps, so old baked edges cannot
make the faces appear inset. Atlas padding is white to prevent dark island
borders bleeding into faces at coarse mip levels. Preparation runs this step
automatically; repeated builds never re-center an already processed image.

Tests cover the published AVIFs as well as the PNG masters, physical reading-frame
anchors, equal lettering heights, complete digit/dot components, residual engraving,
engraving registration/direction, white filtering gutters, flat regular blank maps,
and rebuilding regular dice without stale published blank maps.
