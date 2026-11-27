// Paths are relative to src/assets, the individual dist catalog, and showcase.
export const notices = [
  { catalogs: ['classic'], source: 'LICENSE', output: 'LICENSE', showcase: 'classic/LICENSE' },
  { catalogs: ['cc0'], source: 'cc0/LICENSE', output: 'LICENSE', showcase: 'CC0-LICENSE.txt' },
  { catalogs: ['game-pieces'], source: 'game-pieces/LICENSE', output: 'LICENSE', showcase: 'game-pieces/LICENSE' },
  { catalogs: ['classic', 'cc0'], source: 'fonts/comfortaa/OFL.txt', output: 'licenses/Comfortaa-OFL.txt', showcase: 'licenses/Comfortaa-OFL.txt' },
  { catalogs: ['cc0'], source: 'fonts/dejavu-serif/LICENSE.txt', output: 'licenses/DejaVu-Serif.txt', showcase: 'licenses/DejaVu-Serif.txt' },
  { catalogs: ['cc0'], source: 'cc0/shapes/source/kenney/License.txt', output: 'licenses/Kenney-Board-Game-Icons.txt', showcase: 'licenses/Kenney-Board-Game-Icons.txt' },
  ...['chess', 'checkers'].map((family) => ({
    catalogs: ['game-pieces'], source: 'game-pieces/' + family + '/LICENSE.md',
    output: family + '/LICENSE.md', showcase: 'game-pieces/' + family + '/LICENSE.md',
  })),
];
