from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional, Callable
import numpy as np
import matplotlib.pyplot as plt

# Reduced grids (fast but shape-faithful)
g1_vals = np.linspace(-3, 3, 80)
g2_vals = np.linspace(-3, 3, 80)
G1, G2 = np.meshgrid(g1_vals, g2_vals, indexing="xy")

# MSSM scan dials
tanb_vals = [2, 10, 30]
MS_vals   = np.logspace(np.log10(500), np.log10(6000), 10)
Xt_ratios = np.linspace(0, np.sqrt(6), 10)

v, mt = 246.0, 173.0
pref = (3*mt**4)/(2*np.pi**2*v**2)

best_MS = np.zeros_like(G1)
best_Xr = np.zeros_like(G1)
best_mh = np.zeros_like(G1)

for i in range(G1.shape[0]):
    for j in range(G1.shape[1]):
        g1, g2 = G1[i,j], G2[i,j]
        gY = g1/np.sqrt(5/3)
        mZ2 = (gY**2 + g2**2)*v**2/4

        best = 0
        for tanb in tanb_vals:
            cos2b = np.cos(2*np.arctan(tanb))
            mh2_tree = mZ2*(cos2b**2)
            for MS in MS_vals:
                for Xr in Xt_ratios:
                    delta = pref*(np.log((MS**2)/(mt**2)) +
                                  Xr**2*(1-Xr**2/12))
                    mh = np.sqrt(max(0, mh2_tree + max(0,delta)))
                    score = np.exp(-((mh-125)/3)**2)
                    if score > best:
                        best = score
                        best_MS[i,j] = MS
                        best_Xr[i,j] = Xr
                        best_mh[i,j] = mh

# Plot full M6 fields
fig, axs = plt.subplots(1,2, figsize=(14,6), constrained_layout=True)

im1 = axs[0].imshow(np.log10(best_MS), origin="lower",
                    extent=[g1_vals.min(), g1_vals.max(),
                            g2_vals.min(), g2_vals.max()],
                    cmap="plasma", aspect="auto")
axs[0].set_title("Full M6 field: argmax log10(M_S / GeV)")
axs[0].set_xlabel("g1")
axs[0].set_ylabel("g2")
plt.colorbar(im1, ax=axs[0])

im2 = axs[1].imshow(best_Xr, origin="lower",
                    extent=[g1_vals.min(), g1_vals.max(),
                            g2_vals.min(), g2_vals.max()],
                    cmap="magma", aspect="auto")
axs[1].contour(G1, G2, best_mh, levels=[120,125,130],
               colors="cyan", linewidths=0.8)
axs[1].set_title("Full M6 field: argmax X_t / M_S")
axs[1].set_xlabel("g1")
axs[1].set_ylabel("g2")
plt.colorbar(im2, ax=axs[1])

plt.show()

"""
Clopen strata (discrete matter choices) + bidirectional propagation

- "Layer" = discrete matter content / representation choice.
- Each layer defines beta-function shifts and (optional) thresholds.
- We run a 1-loop gauge RG flow (fast, stable) and provide hooks for:
    - 2-loop RG
    - proper MSSM matching
    - spectrum calculators (SoftSUSY/SPheno/FeynHiggs) integration

Then:
- Downward map: (g1,g2,g3, layer) -> Yukawa proxies -> nuclear stability diagnostics
- Upward map:    (low-energy constants) -> chemistry + stellar fusion windows

This is a scaffold: physics is explicit, but some pieces are "toy parameterizations"
you can replace with real calculations.
"""




# -------------------------
# 0) Utilities
# -------------------------

PI = np.pi

def safe_log(x: float, eps: float = 1e-30) -> float:
    return float(np.log(max(x, eps)))

def clamp(x: float, lo: float, hi: float) -> float:
    return float(min(max(x, lo), hi))

def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


# -------------------------
# 1) Clopen strata (layers)
# -------------------------

@dataclass(frozen=True)
class MatterLayer:
    """
    Discrete stratum (clopen choice).
    Encodes beta-function shifts and optional threshold structure.

    Conventions:
      - We run gauge couplings in GUT-normalized g1 (i.e., g1^2 = (5/3) g_Y^2).
      - 1-loop RG: d(1/alpha_i)/d ln(mu) = - b_i / (2*pi)
        => 1/alpha_i(mu2) = 1/alpha_i(mu1) - (b_i/(2*pi)) ln(mu2/mu1)

    You can define:
      - b: baseline b_i for MSSM or SM depending on your chosen EFT region.
      - db: layer-dependent shift in b_i (extra matter content).
      - thresholds: list of (M_threshold, db_above_threshold) pieces
        so b_i changes when you cross that scale.
    """
    name: str
    # baseline b coefficients for a chosen EFT region (e.g. MSSM 1-loop b = (33/5, 1, -3))
    b_base: Tuple[float, float, float]
    # shifts from extra matter (constant across region unless thresholds specified)
    db_const: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    # thresholds: if provided, piecewise b = b_base + db_const + sum(db_step for thresholds below mu)
    thresholds: List[Tuple[float, Tuple[float, float, float]]] = field(default_factory=list)

    def b_at(self, mu: float) -> Tuple[float, float, float]:
        b = np.array(self.b_base, dtype=float) + np.array(self.db_const, dtype=float)
        for Mth, db in self.thresholds:
            if mu >= Mth:
                b += np.array(db, dtype=float)
        return (float(b[0]), float(b[1]), float(b[2]))


# Example strata:
# MSSM baseline 1-loop b_i = (33/5, 1, -3)
MSSM_BASE = (33.0/5.0, 1.0, -3.0)

# "Extra vectorlike 5 + 5bar" toy shift (illustrative; replace with your exact reps):
# You should compute db from Dynkin indices; this is a placeholder.
VEC_5_5BAR_DB = (1.0, 1.0, 1.0)

LAYERS: Dict[str, MatterLayer] = {
    "MSSM": MatterLayer(name="MSSM", b_base=MSSM_BASE),
    "MSSM+VL(5+5bar)": MatterLayer(name="MSSM+VL(5+5bar)", b_base=MSSM_BASE, db_const=VEC_5_5BAR_DB),
    # Example with a threshold at 10 TeV where extra matter turns on:
    "MSSM+VL@10TeV": MatterLayer(
        name="MSSM+VL@10TeV",
        b_base=MSSM_BASE,
        db_const=(0.0, 0.0, 0.0),
        thresholds=[(1e4, VEC_5_5BAR_DB)]
    ),
}


# -------------------------
# 2) Fast RG engine (1-loop)
# -------------------------

@dataclass
class GaugePoint:
    """Gauge couplings at a scale mu, in GUT-normalized convention for g1."""
    mu: float
    g1: float
    g2: float
    g3: float

    def alphas(self) -> Tuple[float, float, float]:
        return (self.g1**2/(4*PI), self.g2**2/(4*PI), self.g3**2/(4*PI))

    @staticmethod
    def from_alphas(mu: float, a1: float, a2: float, a3: float) -> "GaugePoint":
        return GaugePoint(mu=mu,
                          g1=np.sqrt(4*PI*a1),
                          g2=np.sqrt(4*PI*a2),
                          g3=np.sqrt(4*PI*a3))

def run_gauge_1loop(point: GaugePoint, mu_target: float, layer: MatterLayer, nsteps: int = 64) -> GaugePoint:
    """
    Piecewise integrate 1-loop RG for alpha_i using stepwise b(mu) from the layer.
    We integrate in 1/alpha space for stability.

    For better accuracy with thresholds, we subdivide logarithmically.
    """
    mu0 = point.mu
    if mu_target == mu0:
        return point

    # log-spaced integration direction
    t0 = np.log(mu0)
    t1 = np.log(mu_target)
    ts = np.linspace(t0, t1, nsteps+1)

    a1, a2, a3 = point.alphas()
    inv = np.array([1.0/a1, 1.0/a2, 1.0/a3], dtype=float)

    for k in range(nsteps):
        mu_mid = float(np.exp(0.5*(ts[k] + ts[k+1])))
        dt = float(ts[k+1] - ts[k])
        b1, b2, b3 = layer.b_at(mu_mid)
        bvec = np.array([b1, b2, b3], dtype=float)
        # 1/alpha evolves linearly with t = ln(mu):
        # d(1/alpha)/dt = - b/(2*pi)
        inv += (-bvec/(2*PI))*dt

    a1_t, a2_t, a3_t = (1.0/inv[0], 1.0/inv[1], 1.0/inv[2])
    return GaugePoint.from_alphas(mu=mu_target, a1=a1_t, a2=a2_t, a3=a3_t)


# -------------------------
# 3) M6 fields: your existing argmax, now wrapped per layer
# -------------------------

@dataclass
class HiggsScanConfig:
    tanb_vals: np.ndarray
    MS_vals: np.ndarray
    Xt_ratios: np.ndarray
    v: float = 246.0
    mt: float = 173.0
    mh_target: float = 125.0
    mh_sigma: float = 3.0

def mh_toy_mssm(g1: float, g2: float, tanb: float, MS: float, Xr: float,
                v: float = 246.0, mt: float = 173.0) -> float:
    """
    Very fast toy Higgs mass proxy:
      mh^2 = mZ^2 cos^2(2β) + Δ_stop
    with Δ_stop ~ (3 mt^4)/(2π^2 v^2) [ ln(MS^2/mt^2) + Xr^2(1 - Xr^2/12) ].

    NOTE: This is *not* a full MSSM calculation; it is a placeholder objective.
    """
    # Convert GUT-normalized g1 -> hypercharge gY
    gY = g1 / np.sqrt(5.0/3.0)
    mZ2 = (gY**2 + g2**2)*v**2/4.0

    beta = np.arctan(tanb)
    cos2b = np.cos(2.0*beta)
    mh2_tree = mZ2*(cos2b**2)

    pref = (3.0*mt**4)/(2.0*PI**2*v**2)
    delta = pref*(safe_log((MS**2)/(mt**2)) + Xr**2*(1.0 - Xr**2/12.0))
    mh2 = max(0.0, mh2_tree + max(0.0, delta))
    return float(np.sqrt(mh2))

def argmax_higgs_over_susy(g1: float, g2: float, cfg: HiggsScanConfig) -> Tuple[float, float, float]:
    """
    For fixed (g1,g2), return (MS*, Xr*, mh*).
    """
    best_score = -1.0
    best_MS, best_Xr, best_mh = cfg.MS_vals[0], cfg.Xt_ratios[0], 0.0

    for tanb in cfg.tanb_vals:
        for MS in cfg.MS_vals:
            for Xr in cfg.Xt_ratios:
                mh = mh_toy_mssm(g1, g2, float(tanb), float(MS), float(Xr), v=cfg.v, mt=cfg.mt)
                # Gaussian score around mh_target
                score = np.exp(-((mh - cfg.mh_target)/cfg.mh_sigma)**2)
                if score > best_score:
                    best_score = score
                    best_MS, best_Xr, best_mh = float(MS), float(Xr), float(mh)

    return best_MS, best_Xr, best_mh


# -------------------------
# 4) Downward propagation: Yukawas -> nuclear stability (toy but explicit)
# -------------------------

@dataclass
class DownwardDiagnostics:
    # Yukawa proxies
    yu: float
    yd: float
    ye: float
    # Low-energy masses (toy)
    mu_MeV: float
    md_MeV: float
    me_MeV: float
    # Nuclear stability diagnostics (toy)
    delta_m_np_MeV: float      # neutron-proton splitting proxy
    deuteron_bound_ok: bool    # crude criterion
    hydrogen_stable_ok: bool   # proton stable vs neutron decay regime proxy
    notes: str

def yukawas_from_gauge_and_tanb_toy(g1: float, g2: float, g3: float, tanb: float) -> Tuple[float, float, float]:
    """
    Toy mapping from gauge couplings + tanβ to 1st-gen Yukawa scales.
    Realistically you'd run Yukawa RGEs + thresholds + flavor model.
    Here we just parameterize:
      y ~ y_SM * f(g, tanβ)
    with mild dependence.
    """
    # "SM-ish anchors" (order-of-magnitude at EW scale)
    yu0, yd0, ye0 = 1.3e-5, 2.7e-5, 2.9e-6

    # mild dependence knobs
    gbar = (g1 + g2 + g3)/3.0
    f_g = 1.0 + 0.15*(gbar - 0.65)   # small tilt
    f_tanb_u = 1.0/(np.sin(np.arctan(tanb)) + 1e-9)
    f_tanb_d = 1.0/(np.cos(np.arctan(tanb)) + 1e-9)

    yu = yu0 * f_g * (0.6 + 0.4*clamp(f_tanb_u, 0.5, 4.0))
    yd = yd0 * f_g * (0.6 + 0.4*clamp(f_tanb_d, 0.5, 8.0))
    ye = ye0 * f_g * (0.7 + 0.3*clamp(f_tanb_d, 0.5, 8.0))
    return float(yu), float(yd), float(ye)

def nuclear_stability_from_yukawas_toy(yu: float, yd: float, ye: float,
                                       alpha_em: float = 1/137.036,
                                       LambdaQCD_MeV: float = 200.0) -> DownwardDiagnostics:
    """
    Convert Yukawas -> masses (toy) -> simple nuclear stability heuristics.

    - quark masses: m_q ~ y_q * v / sqrt(2) * sin/cos(beta)
      but beta dependence already folded into y's in our toy map.
    - proton-neutron splitting proxy:
         Δm_np ≈ A*(md - mu) - B*alpha_em*LambdaQCD
      (A,B are toy coefficients).
    - Deuteron bound heuristic: requires pion mass not too large
      and Δm_np not too extreme. We'll proxy with md+mu.
    """
    v = 246000.0  # MeV
    mu = yu * v / np.sqrt(2.0)
    md = yd * v / np.sqrt(2.0)
    me = ye * v / np.sqrt(2.0)

    # toy coefficients
    A = 0.9
    B = 0.8
    delta_m_np = A*(md - mu) - B*alpha_em*LambdaQCD_MeV  # MeV

    # heuristics (very coarse):
    hydrogen_stable_ok = (delta_m_np > 0.3)  # neutron heavier so proton stable
    # deuteron binding tends to fail if pion mass too large; proxy with (mu+md)
    mq_sum = mu + md
    deuteron_bound_ok = (mq_sum < 20.0) and (delta_m_np < 3.0)

    notes = (
        "Toy nuclear checks: Δm_np proxy + mq_sum proxy for pion mass. "
        "Replace with chiral EFT / lattice-informed surrogates if you want real constraints."
    )

    return DownwardDiagnostics(
        yu=yu, yd=yd, ye=ye,
        mu_MeV=float(mu), md_MeV=float(md), me_MeV=float(me),
        delta_m_np_MeV=float(delta_m_np),
        deuteron_bound_ok=bool(deuteron_bound_ok),
        hydrogen_stable_ok=bool(hydrogen_stable_ok),
        notes=notes
    )


# -------------------------
# 5) Upward propagation: chemistry + stellar fusion windows (toy but explicit)
# -------------------------

@dataclass
class UpwardWindows:
    alpha_em: float
    me_over_mp: float
    chemistry_ok: bool
    stellar_pp_ok: bool
    stellar_notes: str
    chemistry_notes: str

def chemistry_window_toy(alpha_em: float, me_MeV: float, mp_MeV: float = 938.272) -> Tuple[bool, str]:
    """
    Chemistry requires:
      - stable atoms with hierarchical scales
      - not-too-strong alpha (relativistic instabilities, different periodic table)
      - reasonable me/mp for molecular structure

    Toy bounds:
      alpha between ~1/180 and ~1/80
      me/mp between ~1e-4 and ~5e-3
    """
    me_over_mp = me_MeV / mp_MeV
    ok = (1/180.0 < alpha_em < 1/80.0) and (1e-4 < me_over_mp < 5e-3)
    notes = (
        f"Toy chemistry window: alpha in (1/180,1/80), me/mp in (1e-4,5e-3). "
        f"Got alpha={alpha_em:.6g}, me/mp={me_over_mp:.6g}."
    )
    return bool(ok), notes

def stellar_fusion_window_pp_toy(alpha_em: float, delta_m_np_MeV: float,
                                 G_scale: float = 1.0) -> Tuple[bool, str]:
    """
    Very coarse proxy for pp-chain viability.

    pp-chain depends on:
      - weak rates (not modeled here),
      - Coulomb barrier ~ alpha_em,
      - nuclear binding / deuteron stability,
      - neutron-proton mass splitting (affects beta processes).

    We'll just gate with:
      alpha not too large,
      delta_m_np not pathological,
      and a "gravity scale" knob (G_scale) to represent stellar core temperatures.

    Replace with a real stellar structure surrogate if you want.
    """
    ok_alpha = (alpha_em < 1/70.0)
    ok_split = (0.2 < delta_m_np_MeV < 5.0)
    # gravity scale affects ability to reach ignition temps
    ok_grav = (0.5 < G_scale < 2.0)

    ok = ok_alpha and ok_split and ok_grav
    notes = (
        f"Toy stellar pp proxy: alpha<1/70, 0.2<Δm_np<5 MeV, 0.5<G_scale<2. "
        f"Got alpha={alpha_em:.6g}, Δm_np={delta_m_np_MeV:.3f}, G_scale={G_scale:.3f}."
    )
    return bool(ok), notes


# -------------------------
# 6) Unified bidirectional map at a base point in your M6 scan
# -------------------------

@dataclass
class FullBundleResult:
    layer: str
    # base gauge data
    mu_UV: float
    g1_UV: float
    g2_UV: float
    g3_UV: float
    mu_IR: float
    g1_IR: float
    g2_IR: float
    g3_IR: float
    # M6 Higgs argmax outputs
    MS_star: float
    Xr_star: float
    mh_star: float
    # downward + upward
    down: DownwardDiagnostics
    up: UpwardWindows

def evaluate_bundle_at_point(
    g1_UV: float,
    g2_UV: float,
    g3_UV: float,
    mu_UV: float,
    mu_IR: float,
    layer: MatterLayer,
    higgs_cfg: HiggsScanConfig,
    alpha_em_override: Optional[float] = None,
    G_scale: float = 1.0,
) -> FullBundleResult:
    """
    The "single fiber" evaluation:
      (g1,g2,g3 at UV, layer) -> run to IR -> Higgs argmax over SUSY dials -> down/up projections
    """
    # 1) Run gauge to IR
    uv = GaugePoint(mu=mu_UV, g1=g1_UV, g2=g2_UV, g3=g3_UV)
    ir = run_gauge_1loop(uv, mu_target=mu_IR, layer=layer)

    # 2) Higgs argmax over SUSY dials (uses IR g1,g2 here)
    MS_star, Xr_star, mh_star = argmax_higgs_over_susy(ir.g1, ir.g2, higgs_cfg)

    # Pick a tanβ representative for Yukawa proxy: you can also pass tanβ* from optimizer if you track it.
    tanb_eff = float(np.median(higgs_cfg.tanb_vals))

    # 3) Downward: Yukawas -> nuclear
    yu, yd, ye = yukawas_from_gauge_and_tanb_toy(ir.g1, ir.g2, ir.g3, tanb_eff)
    alpha_em = float(alpha_em_override) if alpha_em_override is not None else (1/137.036)
    down = nuclear_stability_from_yukawas_toy(yu, yd, ye, alpha_em=alpha_em)

    # 4) Upward: chemistry + stellar windows
    chem_ok, chem_notes = chemistry_window_toy(alpha_em, down.me_MeV)
    stell_ok, stell_notes = stellar_fusion_window_pp_toy(alpha_em, down.delta_m_np_MeV, G_scale=G_scale)
    up = UpwardWindows(
        alpha_em=alpha_em,
        me_over_mp=float(down.me_MeV/938.272),
        chemistry_ok=chem_ok,
        stellar_pp_ok=stell_ok,
        stellar_notes=stell_notes,
        chemistry_notes=chem_notes
    )

    return FullBundleResult(
        layer=layer.name,
        mu_UV=mu_UV, g1_UV=g1_UV, g2_UV=g2_UV, g3_UV=g3_UV,
        mu_IR=mu_IR, g1_IR=ir.g1, g2_IR=ir.g2, g3_IR=ir.g3,
        MS_star=MS_star, Xr_star=Xr_star, mh_star=mh_star,
        down=down, up=up
    )


# -------------------------
# 7) Generating full M6 fields per clopen layer (fast grid runner)
# -------------------------

@dataclass
class FieldGrids:
    g1_vals: np.ndarray
    g2_vals: np.ndarray
    # For each layer: dict of 2D arrays
    MS_star: Dict[str, np.ndarray]
    Xr_star: Dict[str, np.ndarray]
    mh_star: Dict[str, np.ndarray]
    # Optional projections (down/up summary scalars)
    delta_m_np: Dict[str, np.ndarray]
    chemistry_ok: Dict[str, np.ndarray]
    stellar_ok: Dict[str, np.ndarray]

def compute_fields_per_layer(
    g1_vals: np.ndarray,
    g2_vals: np.ndarray,
    g3_fixed: float,
    mu_UV: float,
    mu_IR: float,
    layers: Dict[str, MatterLayer],
    higgs_cfg: HiggsScanConfig,
    alpha_em_override: Optional[float] = None,
    G_scale: float = 1.0,
) -> FieldGrids:
    """
    Computes full unmasked fields over (g1,g2) for each discrete layer.

    Returns:
      MS_star[layer], Xr_star[layer], mh_star[layer] fields
      plus illustrative down/up scalars as additional projections.
    """
    G1, G2 = np.meshgrid(g1_vals, g2_vals, indexing="xy")

    out_MS, out_Xr, out_mh = {}, {}, {}
    out_dmn, out_chem, out_stell = {}, {}, {}

    for lname, layer in layers.items():
        MSf = np.zeros_like(G1, dtype=float)
        Xrf = np.zeros_like(G1, dtype=float)
        mhf = np.zeros_like(G1, dtype=float)
        dmn = np.zeros_like(G1, dtype=float)
        chem = np.zeros_like(G1, dtype=float)
        stell = np.zeros_like(G1, dtype=float)

        # Main loops: keep it simple; if needed, you can numba-jit or parallelize outer i.
        for i in range(G1.shape[0]):
            for j in range(G1.shape[1]):
                res = evaluate_bundle_at_point(
                    g1_UV=float(G1[i, j]),
                    g2_UV=float(G2[i, j]),
                    g3_UV=float(g3_fixed),
                    mu_UV=mu_UV,
                    mu_IR=mu_IR,
                    layer=layer,
                    higgs_cfg=higgs_cfg,
                    alpha_em_override=alpha_em_override,
                    G_scale=G_scale,
                )
                MSf[i, j] = res.MS_star
                Xrf[i, j] = res.Xr_star
                mhf[i, j] = res.mh_star
                dmn[i, j] = res.down.delta_m_np_MeV
                chem[i, j] = 1.0 if res.up.chemistry_ok else 0.0
                stell[i, j] = 1.0 if res.up.stellar_pp_ok else 0.0

        out_MS[lname] = MSf
        out_Xr[lname] = Xrf
        out_mh[lname] = mhf
        out_dmn[lname] = dmn
        out_chem[lname] = chem
        out_stell[lname] = stell

    return FieldGrids(
        g1_vals=g1_vals,
        g2_vals=g2_vals,
        MS_star=out_MS,
        Xr_star=out_Xr,
        mh_star=out_mh,
        delta_m_np=out_dmn,
        chemistry_ok=out_chem,
        stellar_ok=out_stell
    )


# -------------------------
# 8) Minimal "how to run" example
# -------------------------

if __name__ == "__main__":
    # Grid (downsampled fast defaults)
    g1_vals = np.linspace(0.35, 0.65, 60)
    g2_vals = np.linspace(0.45, 0.80, 60)

    # SUSY/Higgs scan config
    higgs_cfg = HiggsScanConfig(
        tanb_vals=np.array([2.0, 10.0, 30.0]),
        MS_vals=np.logspace(np.log10(500.0), np.log10(6000.0), 10),
        Xt_ratios=np.linspace(0.0, np.sqrt(6.0), 10),
    )

    # Choose UV/IR scales for the RG map (editable)
    mu_UV = 2e16   # GUT-ish
    mu_IR = 1e3    # ~1 TeV-ish proxy

    fields = compute_fields_per_layer(
        g1_vals=g1_vals,
        g2_vals=g2_vals,
        g3_fixed=0.7,               # you can also make g3 a grid if you want a 3D base
        mu_UV=mu_UV,
        mu_IR=mu_IR,
        layers=LAYERS,
        higgs_cfg=higgs_cfg,
        alpha_em_override=1/137.036,
        G_scale=1.0,
    )

    # At this point you have:
    # fields.MS_star["MSSM"]          -> 2D array over (g1,g2)
    # fields.MS_star["MSSM+VL(5+5bar)"]
    # etc.
    #
    # Plotting is intentionally not included here to keep this file self-contained.
    # Use imshow/contour on those arrays exactly like your previous code.


def plot_layer_fields_2d(fields, layer_name):
    """
    Quick-look plots for a single clopen layer.
    Produces:
      - log10(MS*)
      - Xt/MS*
      - mh*
      - nuclear delta_m_np
      - chemistry_ok mask
      - stellar_ok mask
    """
    g1_vals = fields.g1_vals
    g2_vals = fields.g2_vals

    extent = [g1_vals.min(), g1_vals.max(),
              g2_vals.min(), g2_vals.max()]

    MS  = fields.MS_star[layer_name]
    Xr  = fields.Xr_star[layer_name]
    mh  = fields.mh_star[layer_name]
    dmn = fields.delta_m_np[layer_name]
    chem = fields.chemistry_ok[layer_name]
    stell = fields.stellar_ok[layer_name]

    fig, axs = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)

    im0 = axs[0,0].imshow(np.log10(MS), origin="lower", extent=extent, aspect="auto", cmap="plasma")
    axs[0,0].set_title(f"{layer_name}: log10(MS*)")
    plt.colorbar(im0, ax=axs[0,0])

    im1 = axs[0,1].imshow(Xr, origin="lower", extent=extent, aspect="auto", cmap="magma")
    axs[0,1].set_title(f"{layer_name}: (Xt/MS)*")
    plt.colorbar(im1, ax=axs[0,1])

    im2 = axs[0,2].imshow(mh, origin="lower", extent=extent, aspect="auto", cmap="viridis")
    axs[0,2].contour(g1_vals, g2_vals, mh, levels=[120,125,130], colors="cyan", linewidths=0.8)
    axs[0,2].set_title(f"{layer_name}: mh* [GeV]")
    plt.colorbar(im2, ax=axs[0,2])

    im3 = axs[1,0].imshow(dmn, origin="lower", extent=extent, aspect="auto", cmap="coolwarm")
    axs[1,0].axhline(0, color="k", lw=0.5)
    axs[1,0].set_title("Δm_np proxy [MeV]")
    plt.colorbar(im3, ax=axs[1,0])

    im4 = axs[1,1].imshow(chem, origin="lower", extent=extent, aspect="auto", cmap="gray_r")
    axs[1,1].set_title("Chemistry OK (1=yes)")
    plt.colorbar(im4, ax=axs[1,1])

    im5 = axs[1,2].imshow(stell, origin="lower", extent=extent, aspect="auto", cmap="gray_r")
    axs[1,2].set_title("Stellar pp OK (1=yes)")
    plt.colorbar(im5, ax=axs[1,2])

    for ax in axs.flat:
        ax.set_xlabel("g1")
        ax.set_ylabel("g2")

    plt.show()

plot_layer_fields_2d(fields, "MSSM")
plot_layer_fields_2d(fields, "MSSM+VL(5+5bar)")

def compute_fields_3d_base(
    g1_vals,
    g2_vals,
    g3_vals,
    mu_UV,
    mu_IR,
    layers,
    higgs_cfg,
    alpha_em_override=None,
    G_scale=1.0,
):
    """
    Computes M6 fields on a 3D base (g1,g2,g3) by stacking 2D slices.

    Returns:
      dict[layer_name] -> dict with keys:
        "MS", "Xr", "mh", "delta_m_np", "chemistry_ok", "stellar_ok"
      each is a 3D array with shape (Ng3, Ng2, Ng1)
    """
    results = {}

    for lname in layers.keys():
        results[lname] = {
            "MS": [],
            "Xr": [],
            "mh": [],
            "delta_m_np": [],
            "chemistry_ok": [],
            "stellar_ok": [],
        }

    for k, g3 in enumerate(g3_vals):
        print(f"[3D base] Computing slice g3 = {g3:.3f} ({k+1}/{len(g3_vals)})")

        fields2d = compute_fields_per_layer(
            g1_vals=g1_vals,
            g2_vals=g2_vals,
            g3_fixed=g3,
            mu_UV=mu_UV,
            mu_IR=mu_IR,
            layers=layers,
            higgs_cfg=higgs_cfg,
            alpha_em_override=alpha_em_override,
            G_scale=G_scale,
        )

        for lname in layers.keys():
            results[lname]["MS"].append(fields2d.MS_star[lname])
            results[lname]["Xr"].append(fields2d.Xr_star[lname])
            results[lname]["mh"].append(fields2d.mh_star[lname])
            results[lname]["delta_m_np"].append(fields2d.delta_m_np[lname])
            results[lname]["chemistry_ok"].append(fields2d.chemistry_ok[lname])
            results[lname]["stellar_ok"].append(fields2d.stellar_ok[lname])

    # stack into arrays
    for lname in layers.keys():
        for key in results[lname]:
            results[lname][key] = np.stack(results[lname][key], axis=0)

    return results


from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

def plot_3d_isosurface_voxels(
    g1_vals,
    g2_vals,
    g3_vals,
    field3d,
    threshold,
    title,
):
    """
    Visualize a 3D admissible region using voxels:
      field3d shape = (Ng3, Ng2, Ng1)
    """
    G3, G2, G1 = np.meshgrid(g3_vals, g2_vals, g1_vals, indexing="ij")
    mask = field3d >= threshold

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    ax.voxels(
        G1, G2, G3,
        mask,
        facecolors="royalblue",
        edgecolor="k",
        alpha=0.25,
    )

    ax.set_xlabel("g1")
    ax.set_ylabel("g2")
    ax.set_zlabel("g3")
    ax.set_title(title)

    plt.show()


# Define 3D base
g3_vals = np.linspace(0.55, 0.85, 10)

fields3d = compute_fields_3d_base(
    g1_vals=g1_vals,
    g2_vals=g2_vals,
    g3_vals=g3_vals,
    mu_UV=mu_UV,
    mu_IR=mu_IR,
    layers=LAYERS,
    higgs_cfg=higgs_cfg,
)

# Example: MSSM Higgs mass admissible volume
mh3d = fields3d["MSSM"]["mh"]

plot_3d_isosurface_voxels(
    g1_vals,
    g2_vals,
    g3_vals,
    mh3d,
    threshold=124.0,
    title="MSSM: mh* ≥ 124 GeV (3D base)",
)

