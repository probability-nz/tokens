import value from "./assets/catalog.json";

export type CatalogPiece = Readonly<{
  name: string;
  rotation: readonly [number, number, number];
  scale: readonly [number, number, number];
  src: string;
}>;

export const catalog = value as unknown as Readonly<{
  attribution: string;
  license: string;
  pieces: readonly CatalogPiece[];
  version: 1;
}>;
