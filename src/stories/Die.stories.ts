import type { Meta, StoryObj } from '@storybook/react';
import { die } from '../assets/die';
import { createAssetStory } from './createAssetStory';

const meta: Meta = {
  title: 'Assets/Die',
  parameters: {
    docs: {
      description: {
        component: `
# ${die.name}

## Properties
- **Scale**: ${die.scale?.join(' × ') ?? 'N/A'}
- **Faces**: ${die.faces?.length || 'N/A'} faces
- **Format**: GLTF with textures
        `
      }
    }
  }
};

export default meta;

export const Default: StoryObj = createAssetStory(die);
