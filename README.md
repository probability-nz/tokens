# Tokens

Reusable glTF pieces. Authoring files live in each asset's `source` directory;
generated assets live beside them. Asset preparation requires ImageMagick with
AVIF and WebP support.

`src/assets/catalog.json` lists the published pieces.

The [complete Play showcase](showcase/release.json) contains all 62 pieces and their published glTF resources.

The original CC BY 4.0 catalog assets were created by Misha Tsyatsko under contract for Garbo Succus.

The [CC0 catalog](src/assets/cc0/catalog.json) contains the tabletop shapes, boards, dominoes, poker chips, Go stones and D100. Models use metres. Copy each glTF with the buffers and textures it references. Variants share resources within their family. Higher-cost meshes use lossless Meshopt compression where it reduces delivery size. Color maps use AVIF at quality 85, matching the legacy dice. Numbered dice use recessed Comfortaa Bold numerals (weight 700). The variable font and its SIL Open Font License are in [src/assets/fonts/comfortaa](src/assets/fonts/comfortaa/). The chips use raised DejaVu Serif Bold numerals. The lettering and domino markings use lossless WebP normal maps. The catalog and models are also built under `dist/cc0/`. The [CC0 dedication](src/assets/cc0/LICENSE) covers this collection.

The [chessmen and checker discs](src/assets/game-pieces/README.md) form a separate CC BY 3.0 catalog under `dist/game-pieces/`. It includes both original attribution notices.

- `pnpm prepare-assets` rebuilds generated assets.
- `pnpm build` validates the catalog and writes `dist`.
- `pnpm dev` builds and starts the catalog preview.
- `pnpm build-storybook` builds the deployable preview.
