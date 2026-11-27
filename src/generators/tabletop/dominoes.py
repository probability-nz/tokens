# SPDX-License-Identifier: CC0-1.0
"""Double-six dominoes: one rounded solid and a seven-face shared atlas."""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from tabletop_art import textures, write_mesh

EXTENT = np.array([.0125, .00425, .025])  # half dimensions, metres
TILE = 768
PIXELS_PER_MM = 28


def pips(number):
    """Coordinates on one 100 × 100 SVG half."""
    points = [(50, 50)] if number % 2 else []
    if number >= 2:
        points.extend([(25, 25), (75, 75)])
    if number >= 4:
        points.extend([(25, 75), (75, 25)])
    if number == 6:
        points.extend([(25, 50), (75, 50)])
    return points


def design(first, second):
    circles = "".join(f'<circle cx="{x}" cy="{y+offset}" r="9.2" fill="#000000"/>'
                      for number, offset in [(first, 0), (second, 100)] for x, y in pips(number))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="25mm" height="50mm" viewBox="0 0 100 200">'
            '<rect x="0" y="0" width="100" height="200" rx="5" fill="#ffffff"/>'
            '<path d="M6.5 100H93.5" stroke="#000000" stroke-width="6.7" stroke-linecap="round"/>'
            + circles + '</svg>')


def atlas(directory):
    albedo = Image.new("RGB", (4*TILE, 2*TILE), (255,255,255))
    normal = Image.new("RGB", albedo.size, (128,128,255))
    rows, cols = np.indices((TILE,TILE), dtype="f")
    x = (cols+.5-TILE/2)/PIXELS_PER_MM
    z = (rows+.5-TILE/2)/PIXELS_PER_MM-12.5
    for number in range(7):
        color = np.zeros((*x.shape,3),"f") + [255,255,255]
        vectors = np.zeros_like(color) + [0,0,1]
        # A rounded line down the centre and spherical pip cavities.
        marks = [((cx-50)/4,(cy-100)/4,2.3,0) for cx,cy in pips(number)]
        for cx, cz, radius, span in [*marks,(0,0,.8375,10.52)]:
            dx = x-cx-np.clip(x-cx,-span,span)
            dz = z-cz
            distance = np.hypot(dx,dz)
            coverage = np.clip((radius-distance)*PIXELS_PER_MM+.5,0,1)
            color += coverage[:,:,None]*([0,0,0]-color)
            strength = np.minimum(.98,distance/radius)*coverage
            gain = strength/np.maximum(distance,.0001)
            mask = distance < radius+.5/PIXELS_PER_MM
            vectors[mask] = np.stack((-gain*dx,-gain*dz,np.sqrt(1-strength**2)),2)[mask]
            lip_width = .27 if span == 0 else .14
            u = (distance-radius)/lip_width
            lip = (u>0) & (u<1)
            slope = (.12/.27)*math.pi*np.sin(2*math.pi*np.clip(u,0,1))
            radial = -slope/np.sqrt(1+slope*slope)
            gain = radial/np.maximum(distance,.0001)
            vectors[lip] = np.stack((gain*dx,gain*dz,np.sqrt(1-radial**2)),2)[lip]
        at = (number%4*TILE,number//4*TILE)
        albedo.paste(Image.fromarray(np.uint8(color.round())), at)
        normal.paste(Image.fromarray(np.uint8(((vectors+1)*127.5).round())), at)
    return textures(directory, albedo, normal)


def rounded_tile():
    """Project the six grid faces onto a box with a 1 mm edge radius."""
    radius = .001
    core = EXTENT-radius
    divisions = []
    for extent, inner in zip(EXTENT,core):
        halfway = inner + radius*(math.sqrt(2)-1)
        divisions.append([-extent,-halfway,-inner,inner,halfway,extent])
    triangles = []
    for axis in range(3):
        a,b = (axis+1)%3,(axis+2)%3
        for sign in (-1,1):
            for i in range(5):
                for j in range(5):
                    quad = []
                    for u,v in [(i,j),(i+1,j),(i+1,j+1),(i,j+1)]:
                        sample = np.zeros(3)
                        sample[axis],sample[a],sample[b] = sign*EXTENT[axis],divisions[a][u],divisions[b][v]
                        inner = np.clip(sample,-core,core)
                        normal = sample-inner
                        normal /= np.linalg.norm(normal)
                        quad.append((inner+radius*normal,normal))
                    if sign < 0:
                        quad.reverse()
                    triangles.extend([[quad[0],quad[1],quad[2]],[quad[0],quad[2],quad[3]]])
    return triangles


def mesh(triangles, numbers):
    positions, normals, uvs, tangents, indices = [], [], [], [], []
    seen = {}

    def vertex(p,n,top,side):
        sign = 1 if side == 0 else -1
        number = numbers[side]
        uv = [((number%4+.5)*TILE+sign*p[0]*1000*PIXELS_PER_MM)/(4*TILE),
              ((number//4+.5)*TILE+(sign*p[2]*1000+12.5)*PIXELS_PER_MM)/(2*TILE)] if top else [.91,.8]
        tangent = np.array([sign,0,0]) if top else np.cross(n,[0,0,1] if abs(n[2])<.9 else [0,1,0])
        tangent = tangent/np.linalg.norm(tangent)
        key = tuple(np.round([*p,*n,*uv,*tangent],9))
        if key not in seen:
            seen[key] = len(positions)
            positions.append(p)
            normals.append(n)
            uvs.append(uv)
            tangents.append([*tangent,-1])
        return seen[key]

    for triangle in triangles:
        top = all(n[1]>.99999 and np.isclose(p[1],EXTENT[1]) for p,n in triangle)
        # Clip at the centre before assigning each half its own atlas cell.
        for side, sign in enumerate([-1,1]):
            polygon = []
            for i,(p,n) in enumerate(triangle):
                q,m = triangle[(i+1)%3]
                if p[2]*sign >= 0:
                    polygon.append((p,n))
                if p[2]*q[2] < 0:
                    t = -p[2]/(q[2]-p[2])
                    cross = p+t*(q-p)
                    cross[2] = 0
                    normal = n+t*(m-n)
                    polygon.append((cross,normal/np.linalg.norm(normal)))
            for i in range(1,len(polygon)-1):
                indices.extend(vertex(*polygon[k],top,side) for k in [0,i,i+1])
    return positions,normals,uvs,tangents,indices


def generate(directory):
    (directory/"source").mkdir()
    images = atlas(directory)
    body = rounded_tile()
    material = dict(pbrMetallicRoughness=dict(baseColorTexture=dict(index=0),metallicFactor=0,
                    roughnessFactor=.4),normalTexture=dict(index=1))
    for first in range(7):
        for second in range(first,7):
            slug = f"{first}-{second}"
            (directory/"source"/(slug+".svg")).write_text(design(first,second))
            write_mesh(directory,slug,"Domino "+slug,mesh(body,(first,second)),images,material,
                       [(-EXTENT).tolist(),EXTENT.tolist()])


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
