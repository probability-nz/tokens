"""Render one shared, bundled typeface in each die face's physical reading frame."""

from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
from dice_style import LABEL_CLEARANCE_MM, LABEL_MAX_HEIGHT_MM, LABEL_FACE_FRACTION

FONT_PATH = Path(__file__).resolve().parents[2] / "src/assets/fonts/ComicNeue-Bold.ttf"
FONT_NAME = "Comic Neue Bold"
# The photographed set has compact numerals and close two-digit spacing.
# These are layout transforms; the redistributed font file is unmodified.
WIDTH_SCALE = 0.90
TRACKING_HEIGHT = 0.04
FONT = ImageFont.truetype(str(FONT_PATH), 1024)


@lru_cache(maxsize=None)
def glyph(label):
    def character(char):
        box = FONT.getbbox(char)
        image = Image.new("L", (box[2] - box[0] + 8, box[3] - box[1] + 8))
        ImageDraw.Draw(image).text((4 - box[0], 4 - box[1]), char, font=FONT, fill=255)
        return image.crop(image.getbbox())

    digits = [character(char) for char in label]
    height = max(im.height for im in digits)
    gap = round(height * TRACKING_HEIGHT)
    width = sum(im.width for im in digits) + gap * (len(digits) - 1)
    body = Image.new("L", (width, height))
    x = 0
    for im in digits:
        body.paste(im, (x, (height - im.height) // 2))
        x += im.width + gap
    if label in ("6", "9"):
        dot = character(".")
        image = Image.new("L", (width + round(height * 0.10) + dot.width, height))
        image.paste(body, (0, 0))
        image.paste(dot, (image.width - dot.width, height - dot.height))
    else:
        image = body
    return image, np.array([(width - 1) / 2, (height - 1) / 2]), height - 1


def render(name, faces, entry, matrix, size=(2048, 2048)):
    """Fit all outcomes together, then rasterize supersampled vector-font masks."""
    mm_per_unit = entry["scale"][0] * 1000
    jobs = []
    for point, polygon, normal, frame in faces:
        centre = np.r_[point, 1] @ frame
        world_polygon = np.c_[polygon, np.ones(len(polygon))] @ frame
        if name == "d4":
            labels = []
            for corner, world_corner in zip(polygon, world_polygon):
                outcome = max(
                    entry["faces"],
                    key=lambda f: (matrix(f["rotation"]) @ world_corner)[1],
                )
                up = world_corner - centre
                up /= np.linalg.norm(up)
                labels.append(
                    (
                        outcome["name"],
                        point + 0.46 * (corner - point),
                        np.array([np.cross(up, normal), -up]).T,
                    )
                )
        else:
            outcome = max(
                entry["faces"], key=lambda f: (matrix(f["rotation"]) @ normal)[1]
            )
            labels = [
                (outcome["name"], point, matrix(outcome["rotation"]).T[:, [0, 2]])
            ]
        for label, anchor_uv, basis in labels:
            image, body_centre, height = glyph(label)
            anchor = np.r_[anchor_uv, 1] @ frame
            polygon_frame = (world_polygon - anchor) @ basis
            y, x = np.nonzero(np.asarray(image) > 127)
            # Glyph coordinates are in fractions of its ink height.
            ink = (np.c_[x, y] - body_centre) / height * [WIDTH_SCALE, 1]
            limit = float("inf")
            for a, b in zip(polygon_frame, np.roll(polygon_frame, -1, axis=0)):
                edge = b - a
                inward = np.array([-edge[1], edge[0]])
                inward /= np.linalg.norm(inward)
                if np.dot(inward, polygon_frame.mean(axis=0) - a) < 0:
                    inward *= -1
                clearance = -np.dot(inward, a) - LABEL_CLEARANCE_MM / mm_per_unit
                reach = -np.min(ink @ inward)
                if reach > 0:
                    limit = min(limit, clearance / reach)
            if limit <= 0:
                raise ValueError(f"{name}: no room for label {label}")
            jobs.append(
                dict(
                    label=label,
                    image=image,
                    body_centre=body_centre,
                    height=height,
                    anchor_uv=anchor_uv,
                    projection=frame[:2] @ basis,
                    limit=limit,
                    face_height=np.ptp(polygon_frame, axis=0)[1],
                )
            )
    common_height = min(
        (4 if name == "d4" else LABEL_MAX_HEIGHT_MM) / mm_per_unit,
        min(j["face_height"] for j in jobs)
        * (0.27 if name == "d4" else LABEL_FACE_FRACTION),
        min(j["limit"] for j in jobs),
    )
    # Draw at 2x atlas resolution, then downsample once. Every glyph starts from
    # the high-resolution TTF raster, never from an earlier die's PNG lettering.
    dimensions = np.array(size) * 2
    canvas = Image.new("L", tuple(dimensions))
    for job in jobs:
        ink_to_world = np.diag([WIDTH_SCALE, 1]) * common_height / job["height"]
        # Pillow's transform maps output pixels to input glyph coordinates.
        transform = (
            np.diag(1 / dimensions) @ job["projection"] @ np.linalg.inv(ink_to_world)
        )
        destination = job["anchor_uv"] * dimensions - 0.5
        offset = job["body_centre"] - destination @ transform
        coefficients = (
            transform[0, 0],
            transform[1, 0],
            offset[0],
            transform[0, 1],
            transform[1, 1],
            offset[1],
        )
        warped = job["image"].transform(
            tuple(dimensions),
            Image.Transform.AFFINE,
            coefficients,
            Image.Resampling.BICUBIC,
        )
        canvas = ImageChops.lighter(canvas, warped)
    canvas = canvas.resize(size, Image.Resampling.LANCZOS)
    return ImageChops.invert(canvas).convert("RGB")
