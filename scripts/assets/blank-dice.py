"""Remove printed/engraved markings from original token maps, without changing meshes.
Requires Pillow, NumPy and SciPy. Usage: python3 scripts/assets/blank-dice.py [tokens checkout]
"""
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image
from scipy import ndimage, sparse
from scipy.sparse.linalg import cg

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else ROOT
OUT = ROOT / 'src/assets/blank-dice'
NAMES = ('d4', 'd6', 'd8', 'd12', 'd20')


def blank(name):
    if name in ('d4', 'd12'):
        # These variants are baked together with their regular numbered mesh.
        return
    folder = SOURCE / 'src/assets' / name / 'source'
    doc = json.loads((folder / f'{name}.gltf').read_text())
    material = doc['materials'][0]
    image_index = doc['textures'][material['normalTexture']['index']]['source']
    normal = Image.open(folder / doc['images'][image_index]['uri']).convert('RGB')
    diffuse_index = doc['textures'][material['pbrMetallicRoughness']['baseColorTexture']['index']]['source']
    diffuse = Image.open(folder / doc['images'][diffuse_index]['uri']).convert('L').resize(normal.size, Image.Resampling.LANCZOS)
    print(name, 'loaded source maps', flush=True)
    # Numerals/pips are dark islands enclosed by light face interiors. Flood out
    # dark atlas background from the border, leaving only the markings.
    dark = np.asarray(diffuse) < 180
    h, w = dark.shape
    labels, count = ndimage.label(dark)
    sizes = np.bincount(labels.ravel())
    keep = (sizes > 0) & (sizes < w*h*.04)
    keep[0] = False
    keep[np.unique(np.concatenate((labels[0],labels[-1],labels[:,0],labels[:,-1])))] = False
    mask = Image.fromarray(keep[labels].astype('uint8') * 255)
    print(name, 'identified markings', flush=True)
    # Include the engraved lip around each glyph, which extends past its ink.
    radius = max(5, round(w / 160))
    bits = np.asarray(mask) > 0
    horizontal = bits.copy()
    for offset in range(1, radius + 1):
        horizontal[:, offset:] |= bits[:, :-offset]
        horizontal[:, :-offset] |= bits[:, offset:]
    expanded = horizontal.copy()
    for offset in range(1, radius + 1):
        expanded[offset:] |= horizontal[:-offset]
        expanded[:-offset] |= horizontal[offset:]
    mask = Image.fromarray(expanded.astype('uint8') * 255)
    # Harmonic interpolation preserves the face's smooth tangent-normal field.
    # A constant flat normal would leave the shape of the erased glyph visible.
    values = np.asarray(normal).astype('float64')
    yy, xx = np.nonzero(expanded)
    count = len(yy)
    ids = np.full((h,w), -1, dtype='int32')
    ids[yy,xx] = np.arange(count)
    rows, cols, weights = [np.arange(count)], [np.arange(count)], [np.full(count,4.)]
    rhs = np.zeros((count,3))
    for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
        ny, nx = np.clip(yy+dy,0,h-1), np.clip(xx+dx,0,w-1)
        neighbour = ids[ny,nx]
        inside = neighbour >= 0
        rows.append(np.flatnonzero(inside))
        cols.append(neighbour[inside])
        weights.append(np.full(np.count_nonzero(inside),-1.))
        rhs[~inside] += values[ny[~inside],nx[~inside]]
    matrix = sparse.csr_matrix((np.concatenate(weights),(np.concatenate(rows),np.concatenate(cols))),shape=(count,count))
    nearest = ndimage.distance_transform_edt(expanded, return_distances=False, return_indices=True)
    initial = values[nearest[0,yy,xx],nearest[1,yy,xx]]
    for channel in range(3):
        solution, info = cg(matrix, rhs[:,channel], x0=initial[:,channel], rtol=1e-6, maxiter=1500)
        if info: raise RuntimeError(f'{name}: map interpolation did not converge ({info})')
        values[yy,xx,channel] = solution
    normal = Image.fromarray(np.clip(np.rint(values),0,255).astype('uint8'))
    normal.save(OUT / f'{name}-blank-normal.png')
    print(name, 'blanked pixels:', np.count_nonzero(np.asarray(mask)), flush=True)


if __name__ == '__main__':
    for name in NAMES:
        blank(name)
    import subprocess
    subprocess.run([sys.executable, str(ROOT / 'scripts/assets/sync-blank-dice.py')], check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/assets/align-dice.py')], check=True)
