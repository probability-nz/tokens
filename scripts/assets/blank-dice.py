"""Remove printed/engraved markings from original token maps, without changing meshes.
Requires Pillow, NumPy and SciPy. Usage: python3 scripts/assets/blank-dice.py [tokens checkout]
"""
import base64
import copy
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
    # Keep the original mesh, indices, normals, UVs, samplers and material settings.
    # Only the albedo/map references change. UVs still serve the original bevels.
    original_normal = copy.deepcopy(material['normalTexture'])
    original_normal['index'] = 0
    sampler = doc['textures'][material['normalTexture']['index']].get('sampler')
    material['normalTexture'] = original_normal
    material['pbrMetallicRoughness'].pop('baseColorTexture')
    material['pbrMetallicRoughness']['baseColorFactor'] = [1,1,1,1]
    doc['textures'] = [{'source': 0, **({'sampler': sampler} if sampler is not None else {})}]
    doc['images'] = [{'uri': f'{name}-blank-normal.png', 'mimeType': 'image/png'}]
    for buffer in doc['buffers']:
        data = (folder / buffer['uri']).read_bytes()
        buffer['uri'] = 'data:application/octet-stream;base64,' + base64.b64encode(data).decode()
    doc['asset']['copyright'] = 'Garbo Succus; source assets by Misha Tsyatsko. CC BY 4.0. Number/pip maps removed; original geometry and bevel shading retained.'
    doc['asset']['extras'] = {'source': 'https://github.com/probability-nz/tokens', 'commit': 'b2559ef7924965d3440478e6b2c54aae79944763'}
    (OUT / f'{name}-blank.gltf').write_text(json.dumps(doc, indent=2) + '\n')
    print(name, 'blanked pixels:', np.count_nonzero(np.asarray(mask)), flush=True)


if __name__ == '__main__':
    for name in NAMES:
        blank(name)
