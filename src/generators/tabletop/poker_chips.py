# SPDX-License-Identifier: CC0-1.0
"""Generate the CC0 39 mm chip mesh and its six original art variants."""
import colorsys
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from tabletop_art import ASSETS, textures, write_mesh

SEGMENTS = 36
PALETTE = {
    "basic": (324, .50, .76), "5": (2, .49, .72), "10": (189, .40, .76),
    "25": (132, .42, .65), "50": (214, .52, .78), "100": (247, .54, .71),
}


def mesh():
    positions, normals, uvs, tangents, indices = [], [], [], [], []

    def vertex(point, normal, uv, tangent):
        positions.append(np.asarray(point) * .001)
        normals.append(normal)
        uvs.append(uv)
        axis = np.asarray(tangent[:3], dtype=float)
        axis -= np.dot(normal, axis) * np.asarray(normal)
        tangents.append([* (axis / np.linalg.norm(axis)), tangent[3]])
        return len(positions) - 1

    def circle(k):
        angle = k * math.tau / SEGMENTS
        return math.sin(angle), -math.cos(angle)

    for sign in (1, -1):
        tangent = [sign, 0, 0, -1]
        center = vertex([0, sign*1.65, 0], [0, sign, 0], [.5, 256/640], tangent)
        rim = []
        for k in range(SEGMENTS):
            x, z = circle(k)
            px, pz = 19.22*x, 19.22*z
            rim.append(vertex([px, sign*1.65, pz], [.2*x, sign*math.sqrt(.96), .2*z],
                              [(256+sign*px*12)/512, (256+pz*12)/640], tangent))
        for k, current in enumerate(rim):
            following = rim[(k+1) % SEGMENTS]
            indices.extend([center, following, current] if sign == 1 else [center, current, following])

    rings = []
    for radius, height, radial, up, v in [
        (19.22, 1.65, .2, math.sqrt(.96), 530), (19.5, 1.37, 1, 0, 545),
        (19.5, -1.37, 1, 0, 605), (19.22, -1.65, .2, -math.sqrt(.96), 620),
    ]:
        ring = []
        for k in range(SEGMENTS+1):
            x, z = circle(k)
            ring.append(vertex([x*radius, height, z*radius], [x*radial, up, z*radial],
                               [k/6, v/640], [-z, 0, x, 1]))
        rings.append(ring)
    for upper, lower in zip(rings, rings[1:]):
        for k in range(SEGMENTS):
            indices.extend([upper[k], upper[k+1], lower[k], upper[k+1], lower[k+1], lower[k]])
    for i in range(0, len(indices), 3):
        a, b, c = indices[i:i+3]
        cross = np.cross(positions[b]-positions[a], positions[c]-positions[a])
        if np.dot(cross, np.sum([normals[a], normals[b], normals[c]], axis=0)) < 0:
            indices[i+1:i+3] = [c, b]
    return positions, normals, uvs, tangents, indices


def smooth(value):
    t = np.clip(value, 0, 1)
    return t*t*(3-2*t)


def sector(angle):
    return smooth((8 - np.abs((angle+30) % 60 - 30)) / 1.3)


def normal_map(height, spacing_y, spacing_x):
    dy, dx = np.gradient(height, spacing_y, spacing_x)
    vectors = np.stack((-dx, -dy, np.ones_like(dx)), axis=2)
    vectors /= np.linalg.norm(vectors, axis=2, keepdims=True)
    return np.uint8(np.round((vectors+1)*127.5))


def design_svg(name, base):
    color = "#" + "".join(f"{round(channel):02x}" for channel in base)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="39mm" height="39mm" viewBox="0 0 100 100">',
             f'<circle cx="50" cy="50" r="49" fill="{color}"/>']
    angle = math.radians(8)
    def point(radius, side):
        return f"{50 + side * radius * math.sin(angle)} {50 - radius * math.cos(angle)}"
    stripe = (f"M{point(49, -1)} A49 49 0 0 1 {point(49, 1)} "
              f"L{point(34, 1)} A34 34 0 0 0 {point(34, -1)}Z")
    for rotation in range(0, 360, 60):
        parts.append(f'<path d="{stripe}" fill="#faf7f0" transform="rotate({rotation} 50 50)"/>')
    if name != "basic":
        parts.append('<text x="50" y="50" dy=".34em" text-anchor="middle" font-family="DejaVu Serif" '
                     f'font-size="26" font-weight="bold" fill="#ffffff">{name}</text>')
    return "".join(parts) + "</svg>"


def generate(directory):
    source = directory / "source"
    source.mkdir(exist_ok=True)
    streams = mesh()
    font = ImageFont.truetype(str(ASSETS / "fonts/dejavu-serif/DejaVuSerif-Bold.ttf"), 132)
    y, x = (np.mgrid[:512, :512] + .5 - 256) / 12
    radius = np.hypot(x, y)
    face = sector(np.rad2deg(np.arctan2(x, -y))) * smooth((radius-13.53)/.35)
    edge = np.broadcast_to(sector((np.arange(512)+.5)*60/512), (128, 512))
    for name, (hue, lightness, saturation) in PALETTE.items():
        base = np.array(colorsys.hls_to_rgb(hue/360, lightness, saturation))*255

        (source / (name + ".svg")).write_text(design_svg(name, base))

        def ink(mask):
            return base + (np.array([250,247,240])-base)*mask[:,:,None]

        glyph = Image.new("L", (512,512))
        if name != "basic":
            draw = ImageDraw.Draw(glyph)
            left, top, right, bottom = draw.textbbox((0,0), name, font=font)
            draw.text((256-(left+right)/2,256-(top+bottom)/2), name, font=font, fill=255)
        rgb = ink(face)
        rgb += (255-rgb)*(np.asarray(glyph)/255)[:,:,None]
        color = Image.fromarray(np.uint8(np.vstack([rgb,ink(edge)]).round()))
        bowl = -1.1*(1-np.clip(radius/13.53,0,1)**6)**2
        height = bowl + .15*face + .18*np.asarray(glyph.filter(ImageFilter.GaussianBlur(1.2)))/255
        normal = Image.fromarray(np.vstack([normal_map(height,1/12,1/12),
                                            normal_map(.15*edge,.05,math.tau*19.5/6/512)]))
        images = textures(directory, color, normal)
        material = dict(name="Chip finish", pbrMetallicRoughness=dict(baseColorFactor=[1,1,1,1],
                        roughnessFactor=.36, metallicFactor=0, baseColorTexture=dict(index=0)),
                        normalTexture=dict(index=1))
        limits = [.0195,.00165,.0195]
        write_mesh(directory,name,"Poker chip "+name.title(),streams,images,material,
                   [[-v for v in limits],limits])


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
