# Tokens

Reusable glTF pieces. Dice are authored in [src/generators/dice](src/generators/dice) and share their geometry and artwork with the React preview. The published catalogs and showcase contain ready-to-load assets.

`src/assets/catalog.json` lists the published pieces.

The [complete Play showcase](showcase/release.json) contains all 67 pieces and their published glTF resources.

The original CC BY 4.0 catalog assets were created by Misha Tsyatsko under contract for Garbo Succus.

The [CC0 catalog](src/assets/cc0/catalog.json) contains the tabletop shapes, boards, dominoes, poker chips, Go stones and D3/D16/D24/D48/D100/D120 dice. Models use metres. Copy each glTF with the buffers and textures it references. Variants share resources within their family. Higher-cost meshes use lossless Meshopt compression where it reduces delivery size. Generated dice use AVIF at quality 75, a small WebP preview and a lossless WebP engraving normal map. Numbered dice use printed Comfortaa Bold numerals (weight 700), consecutive face ordering and rounded edge shading from vertex normals. The variable font and its SIL Open Font License are in [src/assets/fonts/comfortaa](src/assets/fonts/comfortaa/). The chips use raised DejaVu Serif Bold numerals. The chip lettering and domino markings use lossless WebP normal maps. The catalog and models are also built under `dist/cc0/`. The [CC0 dedication](src/assets/cc0/LICENSE) covers this collection.

The [chessmen and checker discs](src/assets/game-pieces/README.md) form a separate CC BY 3.0 catalog under `dist/game-pieces/`. It includes both original attribution notices.

- `pnpm dev:dice` serves the interactive preview at `/dice.html`.
- `pnpm generate:dice` rebuilds the published dice, blank variants, face rotations and showcase records. Install Chromium once with `pnpm exec playwright-core install chromium`. ImageMagick with AVIF and WebP support is required for export.
- `pnpm prepare-assets` rebuilds dice and prepares the other classic assets.
- `pnpm build` validates the catalog and writes `dist`.
- `pnpm dev` builds and starts the catalog preview.
- `pnpm build-storybook` builds the deployable preview.
