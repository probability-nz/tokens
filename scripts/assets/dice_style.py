"""Physical targets for the coordinated dice set, in millimetres.

Nominal sizes follow common commercial polysets (16/18/20 mm). We define size
unambiguously as height above the resting face, rather than an arbitrary model
axis or bounding sphere. These are design targets, not exact Chessex measurements.
"""

HEIGHT_MM = {"die": 16, "d4": 16, "d6": 16, "d8": 16, "d10": 16, "d12": 18, "d20": 20}
FILLET_MM = 1.2
LABEL_CLEARANCE_MM = 0.45
LABEL_MAX_HEIGHT_MM = 7.0
LABEL_FACE_FRACTION = 0.60
ENGRAVING_ROUNDING_MM = 0.25
ENGRAVING_SMOOTHING_MM = 0.04
ENGRAVING_DEPTH_MM = 0.18
PIP_DEPTH_MM = 0.35
