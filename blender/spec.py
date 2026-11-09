"""Dudi build spec: every dimension and colour in one place.

Units: 1.0 = sole to crown (top of the cap). Blender Z-up, Dudi faces -Y,
his left side is +X. Measurements come from the master sheet (see
reference/sheet_measurements.json); values marked (sheet) were read off it.
"""

H = 1.0

# ---------------------------------------------------------------- palette
# Starting values from the brief; corrected against the sheet by probe in
# tools/calibrate.py. sRGB hex.
PALETTE = {
    'fur': '#E8761E',
    'cream': '#F2DDB0',
    'ear_tip': '#4A2A18',
    'cap': '#7A2238',
    'denim': '#4F7DB0',
    'hoodie': '#F6CF14',
    'pants': '#7A5A3A',
    'sneakers': '#C4322C',
    'backpack': '#7A4A2A',
    'hands': '#5A3420',
    # supporting colours (sheet)
    'nose': '#4A2620',
    'brow': '#9A4A1C',
    'iris': '#9A5424',
    'iris_rim': '#3A1A0C',
    'eye_white': '#F6F2EA',
    'sole': '#F2EFE8',
    'stitch_denim': '#D89A4A',
    'stitch_pants': '#9C7A52',
    'button': '#B87A4A',
    'zip': '#C8C8C8',
    'mouth': '#5A1A1E',
    'tongue': '#D8676E',
    'teeth': '#FAF6EE',
    'lace': '#F4F1EA',
}

# ---------------------------------------------------------------- landmarks (sheet)
CROWN_Z = 1.0          # top of cap
EAR_TIP = (0.205, 0.09, 1.088)
EYE_C = (0.077, -0.097, 0.776)  # eyeball centre (L side, mirror for R)
EYE_R = 0.046
EYE_SOCKET_R = 0.0505
NOSE_C = (0.0, -0.196, 0.709)
MOUTH_CORNER = (0.08, None, 0.693)
MOUTH_CENTER_Z = 0.664
CHIN_Z = 0.615         # top of the hood at the centre line (sheet chin line)
HOOD_TOP_Z = 0.615
JACKET_HEM_Z = 0.300
HOODIE_HEM_Z = 0.266
CUFF_Z = 0.336
PANTS_HEM_Z = 0.088
CUFF_ROLL_TOP_Z = 0.132
SHOE_TOP_Z = 0.080

# skeleton joints (rest pose = sheet front view), left side
SHOULDER = (0.125, 0.0, 0.505)
ELBOW = (0.163, 0.012, 0.418)
WRIST = (0.183, 0.002, 0.338)
HAND_C = (0.19, 0.0, 0.29)
HIP = (0.062, 0.005, 0.255)
KNEE = (0.066, -0.004, 0.150)
ANKLE = (0.076, 0.004, 0.058)

TAIL_PTS = [  # (y, z) on the centre line, side view (sheet)
    (0.070, 0.305), (0.140, 0.272), (0.210, 0.270), (0.280, 0.298),
    (0.325, 0.360), (0.335, 0.440), (0.325, 0.520), (0.310, 0.575),
]
TAIL_R = [0.032, 0.050, 0.062, 0.072, 0.079, 0.079, 0.070, 0.045]
TAIL_CREAM_FROM = 0.64   # fraction of tail length where the cream tip starts

FUR_LEN = {
    'head': 0.011, 'cheek': 0.03, 'nape': 0.02, 'ear': 0.006, 'ear_inner': 0.014,
    'tail': 0.03, 'hand': 0.006,
}

# ---------------------------------------------------------------- cap (backward)
# Crown = half-ellipsoid on a base plane tilted back by CAP_TILT_DEG (front edge higher).
CAP_C0 = (0.0, 0.035, 0.838)      # centre of the base ellipse
CAP_TILT_DEG = 16.5
CAP_R_OUT = (0.170, 0.190, 0.168)  # x, along-plane y, dome height
CAP_THICK = 0.0045
CAP_BRIM_LEN = 0.175
CAP_BRIM_DROP_DEG = 16.0          # extra downward angle of the brim relative to the base plane
