import catalog from './assets/catalog.json';

export { catalog };
export type CatalogPiece = (typeof catalog.pieces)[number];
