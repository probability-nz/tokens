import type { Meta, StoryObj } from '@storybook/react';
import { pawn } from '../assets/pawn';
import { createAssetStory } from './createAssetStory';

const meta: Meta = {
  title: 'Assets/pawn',
  parameters: {
    docs: {
      description: {
        component: `
# ${pawn.name}

## Properties
- **Scale**: ${pawn.scale?.join(' × ') ?? 'N/A'}
- **Format**: GLTF with textures
        `
      }
    }
  }
};

export default meta;

export const Default: StoryObj = createAssetStory(pawn, 'pawn');
