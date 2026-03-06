#!/usr/bin/env python3
"""
mssm_intersection_mc.py

Compute a 3D MSSM base (g1,g2,g3), intersect multiple constraints,
and extract the boundary manifold using marching cubes.

This file is self-contained and avoids matplotlib.voxels entirely.
"""

from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from skimage.measure import marching_cubes

# ------------------------------------------------------------
# 1) Grids (moderate resolution, safe to increase later)
# ------------------------------------------------------------

g1_vals = np.linspace(0.35, 0.65, 60)
g2_vals = np.linspace(0.45, 0.80, 60)
g3_vals = np.linspace(0.55, 0.85, 10)

G3, G2, G1 = np.meshgrid(g3_vals, g2_vals, g1_vals, indexing="ij")

# ------------------------------------------------------------
# 2) Toy MSSM Higgs proxy + auxiliary fields
# ------------------------------------------------------------

def mh_toy(g1, g2, g3):
    """
    Smooth Higgs-like scalar field.
    Replace this with your real mh* field if desired.
    """
    return (
        122
        + 6.0 * np.exp(
            -((g1 - 0.50)**2 / 0.010
              + (g2 - 0.60)**2 / 0.020
              + (g3 - 0.70)**2 / 0.010)
        )
        - 2.0 * (g3 - 0.70)**2
    )

def MS_star(g2, g3):
    """Toy argmax M_S* field"""
    return 10.0 ** (3.0 + 0.6*(g2 - 0.6) - 0.4*(g3 - 0.7))

def Xr_star(g1):
    """Toy argmax Xt/MS field"""
    return 2.0 + 1.5*(g1 - 0.5)

# Compute fields
mh3d  = mh_toy(G1, G2, G3)
MS3d  = MS_star(G2, G3)
Xr3d  = Xr_star(G1)

# ------------------------------------------------------------
# 3) Downward / upward gates (toy but explicit)
# ------------------------------------------------------------

# Chemistry gate
chem_ok = (
    (1/180.0 < 1/137.036) &
    (1/137.036 < 1/80.0)
)

chem3d = np.ones_like(mh3d) if chem_ok else np.zeros_like(mh3d)

# Stellar gate (simple window in g3)
stell3d = ((g3_vals[:, None, None] > 0.58) &
           (g3_vals[:, None, None] < 0.80)).astype(float)

# ------------------------------------------------------------
# 4) Intersection mask
# ------------------------------------------------------------

mask = (
    (mh3d >= 124.0) &
    (chem3d >= 0.5) &
    (stell3d >= 0.5)
)

print("Admissible voxels:", mask.sum(), "/", mask.size)

# ------------------------------------------------------------
# 5) Marching cubes on the INTERSECTION
# ------------------------------------------------------------

vol = mask.astype(np.float32)

verts, faces, _, _ = marching_cubes(vol, level=0.5)

# Map index coordinates -> physical coordinates
zi, yi, xi = verts.T

x = np.interp(xi, np.arange(len(g1_vals)), g1_vals)
y = np.interp(yi, np.arange(len(g2_vals)), g2_vals)
z = np.interp(zi, np.arange(len(g3_vals)), g3_vals)

# Sample fiber values on the boundary
xi_i = np.clip(np.round(xi).astype(int), 0, len(g1_vals)-1)
yi_i = np.clip(np.round(yi).astype(int), 0, len(g2_vals)-1)
zi_i = np.clip(np.round(zi).astype(int), 0, len(g3_vals)-1)

mh_vals = mh3d[zi_i, yi_i, xi_i]
logMS   = np.log10(MS3d[zi_i, yi_i, xi_i])
Xr_vals = Xr3d[zi_i, yi_i, xi_i]

# ------------------------------------------------------------
# 6) Plots
# ------------------------------------------------------------

def plot_surface(cvals, cmap, title, cbar_label):
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    surf = ax.plot_trisurf(
        x, y, z,
        triangles=faces,
        cmap=cmap,
        shade=False
    )
    surf.set_array(cvals)
    surf.autoscale()

    ax.set_xlabel("g1")
    ax.set_ylabel("g2")
    ax.set_zlabel("g3")
    ax.set_title(title)

    fig.colorbar(surf, ax=ax, shrink=0.6, label=cbar_label)
    plt.tight_layout()
    plt.show()

# Boundary colored by mh*
plot_surface(
    mh_vals,
    cmap="viridis",
    title="Boundary of (mh ≥ 124) ∩ chemistry ∩ stellar",
    cbar_label="mh* [GeV]"
)

# Boundary colored by log10(MS*)
plot_surface(
    logMS,
    cmap="plasma",
    title="Same boundary colored by log10(M_S*)",
    cbar_label="log10(M_S*)"
)

# Reduced admissible manifold (graph of section)
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection="3d")
sc = ax.scatter(
    x, y, logMS,
    c=Xr_vals,
    cmap="magma",
    s=6
)
ax.set_xlabel("g1")
ax.set_ylabel("g2")
ax.set_zlabel("log10(M_S*)")
ax.set_title("Reduced admissible manifold (section)")
fig.colorbar(sc, ax=ax, label="(X_t/M_S)*")
plt.tight_layout()
plt.show()
