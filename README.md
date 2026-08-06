# Probability tokens

Reusable glTF pieces for Probability. The public boundary is
[`catalog.json`](src/assets/catalog.json): a versioned list of relative model
paths with default scale and rotation in radians. Games store the resolved
model URL as an ordinary piece `src`; this package has no gameplay API.

`pnpm build` validates the catalog and every referenced glTF resource, then
copies only that reachable asset graph to `dist`. `pnpm build-storybook`
previews the same output.

Original authoring files live in each piece's `source` directory. After changing
one, run `pnpm prepare-assets` with ImageMagick built with AVIF and WebP support,
then commit the generated glTF and images. Textured pieces author a small WebP
preview/fallback and an AVIF preferred image; normal maps use lossless WebP.
