"""Exact pentagonal trapezohedron planes and symmetry-derived reading poses.

Ten congruent kite faces at equal distances from the origin. The axial normal
component controls elongation; 1/sqrt(3) gives a compact gaming-die proportion.
See https://mathworld.wolfram.com/Trapezohedron.html for the construction.
"""

import math

INRADIUS = 0.6
AXIAL = 1 / math.sqrt(3)
RADIAL = math.sqrt(1 - AXIAL * AXIAL)
# Interleaved caps read 0,7,4,1,6,9,2,5,8,3. Opposite labels sum to nine.
LABELS = ("0", "4", "6", "2", "8", "7", "1", "9", "5", "3")


def normals():
    return [
        (RADIAL * math.cos(theta), sign * AXIAL, RADIAL * math.sin(theta))
        for sign, offset in ((1, 0), (-1, math.pi / 5))
        for theta in (2 * k * math.pi / 5 + offset for k in range(5))
    ]


def poses():
    tilt = math.acos(AXIAL)
    result = []
    for i, label in enumerate(LABELS):
        # Compose the ten rotational symmetries algebraically. Retain exact
        # 18-degree yaw steps and zero Z rotation instead of fitting noisy mesh
        # planes or converting through Euler singularities.
        step = (-5 if i < 5 else 7) + 4 * (i % 5)
        step = (step + 10) % 20 - 10
        result.append(
            {
                "name": label,
                "rotation": [
                    -tilt if i < 5 else math.pi - tilt,
                    step * math.pi / 10,
                    0,
                ],
            }
        )
    return sorted(result, key=lambda f: int(f["name"]))
