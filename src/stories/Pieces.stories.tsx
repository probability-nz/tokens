import type { Meta, StoryObj } from '@storybook/react-vite';
import { catalog, type CatalogPiece } from '../catalog';
import { PiecePreview } from './PiecePreview';

const meta = {
  title: 'Pieces',
  component: PiecePreview,
  args: { piece: catalog.pieces[0], view: 'Perspective' },
  argTypes: {
    piece: {
      control: 'select',
      mapping: Object.fromEntries(
        catalog.pieces.map((piece) => [piece.name, piece]),
      ),
    },
    view: { control: 'inline-radio', options: ['Perspective', 'Top'] },
  },
} satisfies Meta<{ piece: CatalogPiece; view: 'Perspective' | 'Top' }>;

export default meta;

type Story = StoryObj<typeof meta>;

const story = (name: CatalogPiece['name']): Story => {
  const piece = catalog.pieces.find((candidate) => candidate.name === name);
  if (piece === undefined) throw new Error(`Missing ${name} from the catalog`);
  return { args: { piece } };
};

export const Pawn = story('Pawn');
export const ClassicDie = { ...story('Classic die'), name: 'Classic die' };
export const D4 = { ...story('D4'), name: 'D4' };
export const D6 = { ...story('D6'), name: 'D6' };
export const D8 = { ...story('D8'), name: 'D8' };
export const D12 = { ...story('D12'), name: 'D12' };
export const D20 = { ...story('D20'), name: 'D20' };
