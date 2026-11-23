# Tokens

Reusable glTF pieces. Authoring files live in each asset's `source` directory;
generated assets live beside them. Asset preparation requires ImageMagick with
AVIF and WebP support.

`src/assets/catalog.json` lists the published pieces.

The pieces in the original catalog were created by Misha Tsyatsko under contract for Garbo Succus.

The separate [playing-card manifest](src/assets/playing-cards/austin/deck.json) lists a poker-sized deck with a shared blue back. Each card uses Play’s 63.5 × 88.9 × 0.3 mm poker geometry and 12 px/mm AVIF artwork (762 × 1067 pixels). Run `node scripts/prepare-playing-cards.mjs` with Inkscape and ImageMagick to regenerate the textures, models and manifest. The SVG originals and shared glTF template are in the deck’s `source` directory. [Artwork license and source](src/assets/playing-cards/austin/LICENSE.md)

- `pnpm prepare-assets` rebuilds generated assets.
- `pnpm build` validates the catalog and writes `dist`.
- `pnpm dev` builds and starts the catalog preview.
- `pnpm build-storybook` builds the deployable preview.
