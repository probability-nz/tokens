import type { Meta, StoryObj } from "@storybook/react";
import { catalog, type CatalogPiece } from "../catalog";
import { Asset } from "./createAssetStory";

const meta = {
  title: "Pieces",
  component: Asset,
  args: { piece: catalog.pieces[0], view: "Perspective" },
  argTypes: {
    piece: { control: "select", mapping: Object.fromEntries(catalog.pieces.map((piece) => [piece.name, piece])) },
    view: { control: "inline-radio", options: ["Perspective", "Top"] },
  },
} satisfies Meta<{ piece: CatalogPiece; view: "Perspective" | "Top" }>;

export default meta;

export const Catalog: StoryObj<typeof meta> = {};
