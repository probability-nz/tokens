import type { Meta, StoryObj } from '@storybook/react-vite';
import { catalog, type CatalogPiece } from '../catalog';
import { PiecePreview, type PreviewQuality } from './PiecePreview';

const meta = {
  title: 'Pieces',
  component: PiecePreview,
  args: {
    face: catalog.pieces[0].faces[0]?.name ?? 'None',
    piece: catalog.pieces[0],
    quality: 'High',
    view: 'Perspective',
  },
  argTypes: {
    face: { control: 'select' },
    piece: { control: false },
    quality: { control: 'inline-radio', options: ['High', 'Preview'] },
    view: { control: 'inline-radio', options: ['Perspective', 'Top'] },
  },
} satisfies Meta<{
  face: string;
  piece: CatalogPiece;
  quality: PreviewQuality;
  view: 'Perspective' | 'Top';
}>;

export default meta;

type Story = StoryObj<typeof meta>;

const story = (name: CatalogPiece['name']): Story => {
  const piece = catalog.pieces.find((candidate) => candidate.name === name);
  if (piece === undefined) throw new Error(`Missing ${name} from the catalog`);
  return {
    args: { face: piece.faces[0]?.name ?? 'None', piece },
    argTypes: {
      face: {
        control: 'select',
        options: [...piece.faces.map((face) => face.name), 'None'],
      },
    },
  };
};

export const ClassicDie = { ...story('Classic die'), name: 'Classic die' };
export const D4 = { ...story('D4'), name: 'D4' };
export const D6 = { ...story('D6'), name: 'D6' };
export const D8 = { ...story('D8'), name: 'D8' };
export const D12 = { ...story('D12'), name: 'D12' };
export const D20 = { ...story('D20'), name: 'D20' };
export const Pawn = story('Pawn');
