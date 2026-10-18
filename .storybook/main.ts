import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  staticDirs: ['../dist'],
  viteFinal(viteConfig) {
    // Allow a shared pnpm store when developing in an isolated worktree.
    viteConfig.server ??= {};
    viteConfig.server.fs ??= {};
    viteConfig.server.fs.allow = [
      ...(viteConfig.server.fs.allow ?? []),
      fileURLToPath(new URL('..', import.meta.url)),
      realpathSync(new URL('../node_modules/.pnpm', import.meta.url)),
    ];
    return viteConfig;
  },
};

export default config;
