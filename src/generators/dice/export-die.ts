// Browser-only export boundary: the preview and the catalog use identical font metrics and rasterization.
import { Euler } from 'three';
import { createDieResources } from './render-die';
import type { Kind } from './shapes';

export async function loadExportFont() {
  const url = new URL(
    '../../assets/fonts/comfortaa/Comfortaa[wght].ttf',
    import.meta.url,
  );
  const font = await new FontFace('Comfortaa', 'url(' + url.href + ')', {
    weight: '300 700',
  }).load();
  document.fonts.add(font);
}

export function exportDie(kind: Kind) {
  const die = createDieResources(kind);
  try {
    const attribute = (name: string) =>
      Array.from(die.geometry.getAttribute(name).array);
    return {
      position: attribute('position'),
      normal: attribute('normal'),
      uv: attribute('uv'),
      faces: die.faces.map((f) => ({
        name: f.name,
        rotation: new Euler().setFromQuaternion(f.pose).toArray().slice(0, 3),
      })),
      color: (die.marked.map!.image as HTMLCanvasElement)
        .toDataURL('image/png')
        .split(',')[1],
      relief: (die.marked.normalMap!.image as HTMLCanvasElement)
        .toDataURL('image/png')
        .split(',')[1],
    };
  } finally {
    die.dispose();
  }
}
