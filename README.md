# Tokens

Reusable glTF pieces. Authoring files live in each asset's `source` directory;
generated assets live beside them. Asset preparation requires ImageMagick with
AVIF and WebP support.

Assets were created by Misha Tsyatsko under contract for Garbo Succus.

- `pnpm prepare-assets` rebuilds generated assets.
- `pnpm build` validates the catalog and writes `dist`.
- `pnpm build-storybook` previews the published assets.
