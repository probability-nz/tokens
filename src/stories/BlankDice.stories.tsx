import type { Meta, StoryObj } from '@storybook/react-vite';
import { BlankDicePreview } from './BlankDicePreview';
const meta = {
  title: 'Assets/Blank Dice',
  component: BlankDicePreview,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof BlankDicePreview>;
export default meta;
type Story = StoryObj<typeof meta>;
export const FullSet: Story = {};
