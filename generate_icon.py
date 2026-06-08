#!/usr/bin/env python3
"""Generate the processing_gflex plugin icon.

Computes the exact 2-D point-load flexure solution (Kelvin kei function)
on a 24×24 pixel grid, colours it with a diverging palette derived from
the gFlex RTD logo, and saves a 192×192 PNG (each cell = 8×8 px).

Run from the repo root:
    python generate_icon.py
"""

import numpy as np
from scipy.special import kei
from PIL import Image

# ── Physical parameters ───────────────────────────────────────────────────────
Te    = 2000.       # elastic thickness [m] — thin plate → compact forebulge ring
E     = 65e9
nu    = 0.25
rho_m = 3300.
g     = 9.8
D     = E * Te**3 / (12 * (1 - nu**2))
alpha = (D / (rho_m * g))**0.25   # ≈ 6.1 km

# ── Grid: 24×24 cells at 3 km → forebulge ring at r ≈ 10 cells ───────────────
n  = 24
dx = 3000.
cx = cy = (n - 1) / 2.0   # fractional cell index of centre

ix = np.arange(n, dtype=float)
iy = np.arange(n, dtype=float)
XX, YY = np.meshgrid(ix, iy)

r_arr  = np.sqrt((XX - cx)**2 + (YY - cy)**2) * dx
r_safe = np.maximum(r_arr, dx * 0.05)   # avoid singularity at r=0

w = kei(r_safe / alpha)   # w < 0 = depression, w > 0 = forebulge
w_min, w_max = w.min(), w.max()

# ── Two-part colourmap mapping ────────────────────────────────────────────────
# Depression [w_min, 0] → colormap [0.00, 0.55]  (navy → near-white)
# Forebulge  [0, w_max] → colormap [0.55, 1.00]  (near-white → crimson)
# This gives the forebulge 45% of the colour range despite being 1.6% of
# the physical amplitude, so it reads clearly at icon scale.
t = np.where(w <= 0,
             0.55 * (w - w_min) / (0.0 - w_min),    # w_min→0 : t 0→0.55
             0.55 + 0.45 * (w / w_max))              # 0→w_max : t 0.55→1.00

# ── Colour ramp — palette from the gFlex RTD logo ─────────────────────────────
# Stops:   t   →  (R, G, B)
_stops = [
    (0.00, (0.10, 0.16, 0.51)),   # deep navy       (large depression)
    (0.25, (0.24, 0.53, 0.80)),   # sky blue
    (0.40, (0.53, 0.77, 0.92)),   # pale blue
    (0.55, (0.97, 0.97, 0.97)),   # near-white       (zero crossing)
    (0.70, (0.91, 0.53, 0.37)),   # warm orange
    (0.85, (0.82, 0.25, 0.16)),   # warm red
    (1.00, (0.52, 0.04, 0.06)),   # deep crimson     (forebulge peak)
]


def sample_ramp(t_val):
    """Interpolate the colour ramp at scalar t_val ∈ [0, 1]."""
    for i in range(len(_stops) - 1):
        t0, c0 = _stops[i]
        t1, c1 = _stops[i + 1]
        if t_val <= t1:
            f = (t_val - t0) / (t1 - t0)
            return tuple(c0[j] + f * (c1[j] - c0[j]) for j in range(3))
    return _stops[-1][1]


# Vectorised colour lookup
t_flat = t.ravel()
rgb = np.array([sample_ramp(float(v)) for v in t_flat]).reshape(n, n, 3)
rgb = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)

# ── Load marker: dark grey centre cell ────────────────────────────────────────
ci = n // 2
rgb[ci - 1 : ci + 1, ci - 1 : ci + 1] = (30, 30, 35)

# ── Upscale to 192×192 (8×8 block per cell) — nearest-neighbour ───────────────
cell = 8
img_large = np.repeat(np.repeat(rgb, cell, axis=0), cell, axis=1)

out_path = 'processing_gflex/icons/icon.png'
Image.fromarray(img_large).save(out_path)
print(f"Saved {img_large.shape[1]}×{img_large.shape[0]} px → {out_path}")
print(f"α = {alpha/1e3:.1f} km  |  forebulge at r ≈ {alpha * 4.93 / dx:.1f} cells")
print(f"w range: {w_min:.4f} to {w_max:.4f}  |  forebulge = {w_max/abs(w_min)*100:.1f}% of depression")
