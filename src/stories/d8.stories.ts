import type { Meta, StoryObj } from '@storybook/react';
import { d8 } from '../assets/d8';
import { createAssetStory } from './createAssetStory';

const meta: Meta = {
  title: 'Assets/d8',
  parameters: {
    docs: {
      description: {
        component: `
# ${d8.name}

## Properties
- **Scale**: ${d8.scale?.join(' × ') ?? 'N/A'}
- **Faces**: ${d8.faces?.length || 'N/A'} faces
- **Format**: GLTF with textures
        `
      }
    }
  }
};

export default meta;

export const Default: StoryObj = createAssetStory(d8, 'd8');
