# Lorentz Invariance & Emergent Locality: Draft Target

This is a concrete starting point for the "Lorentz invariance & emergent
locality" direction, framed in the projection -> covariance -> MDL pipeline.

---

## 1) Latent structure class

Define a minimal microstructure family that can encode Lorentz-violating (LIV)
effects but does not force them to survive projection.

Proposed class:

* Discrete causal structures with a tunable anisotropy parameter.
* Two-scale correlation injections:
  * short-range isotropic correlations;
  * long-range anisotropy or direction-dependent breakpoints.
* Optional ultrametric (valuation-depth) hierarchy as a hidden layer.

Minimal parameterization:

* Anisotropy strength: `a` (0 = isotropic, >0 = anisotropic).
* Directional breakpoint: `x_b` (scale where anisotropy switches on).
* Hierarchy depth: `d` (valuation depth or number of discrete levels).

---

## 2) Observation channel

Define what the "universe" or experiment actually observes. In this framework,
LIV is not a statement about the latent rule, but about which projections can
resolve it under covariance.

Observation channels to include (minimal set):

* 1D inclusive spectra (energy or pT distributions).
* Two-point correlation observables with angular resolution (adjacency).
* Diffusion / scale-local projections (cumulative or log-diff transforms).

Noise/covariance:

* Use the existing covariance pipeline; LIV is detectable only if it survives
  the projection + covariance channel.

---

## 3) Invariants to test

Define observables that are stable under the projection pipeline when LIV is
absent, and change in a measurable way when LIV survives.

Candidate invariants:

* Projection-stable scaling exponent (single effective exponent under global
  spectra).
* Anisotropy-sensitive residuals under angular correlation projections.
* Scale-local asymmetry statistic:
  * compare log-derivative signatures across angular bins.

Each invariant should be defined so that the null (Lorentz invariance) is a
single-parameter basin under MDL.

---

## 4) Falsifiable prediction

Core prediction:

* A broad class of discrete/ultrametric microstructures will show no LIV in
  1D spectra under realistic covariance, even when anisotropy exists in truth.

Specific falsifiable signatures:

1) If LIV is present at all, it will appear first in adjacency/correlation
   probes (angular or diffusion-style), not in inclusive 1D spectra.
2) For fixed `a` and `x_b`, detectability is non-monotonic in valuation depth
   `d` due to projection aliasing; there exists a mid-depth regime where true
   LIV is collapsed into a single effective exponent.
3) A change in projection (e.g., cumulative or log-diff) will shift the
   detectability threshold in `a` without changing the null basin.

Operational test:

* Sweep `a`, `x_b`, and `d` in the harness; compare MDL preference for:
  * Model A: isotropic single-parameter fit.
  * Model B: anisotropic two-parameter fit.
* Report `epsilon_50` and `epsilon_90` thresholds per projection channel.

---

## 5) Immediate next steps

1) Implement a minimal anisotropy injection (direction-dependent breakpoints).
2) Add an angular correlation projection alongside the existing 1D spectra.
3) Run detectability scans across `a`, `x_b`, `d` for each projection.
4) Summarize which channels resolve LIV first and where aliasing hides it.
