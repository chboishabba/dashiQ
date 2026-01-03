# MDL Mapping: Allowed vs Supported Structure

## Motivation: Allowed vs Supported

The Standard Model Lagrangian enumerates all symmetry-allowed renormalizable
interactions for a chosen field content. This defines a hypothesis space of
allowed structures, not a data-driven truncation. Real data, however, are
finite, correlated, and noisy. The question we answer is:

How much functional structure does the data actually pay for?

We separate:

- Allowed: all symmetry-permitted terms (prior to data).
- Supported: the empirically justified subspace under full covariance.

This note formalizes the mapping from allowed to supported structure using
minimal description length (MDL) at the observable level.


## Observable-Level Hypothesis Families

For each observable O(x), we define nested families of shapes:

    y(x) = y_ref(x) * exp(log_a + b u + c u^2),  u = basis(x)

Models:

- A: log_a only (normalization).
- B: log_a + b u (add one shape DOF).
- C: log_a + b u + c u^2 (add curvature).

The basis is part of the hypothesis family. For continuous spectra we use a
log-spectral basis u = log(x/x0). For ordinal/discrete observables, we use an
ordinal basis u = x - x0. Here y_ref(x) = 1 unless a theory baseline is
explicitly provided.

This framing does not assume an SM prediction; it tests minimal shape
complexity supported by the data itself.


## Projection Loop as a Lossy Channel

Physics models specify an allowed hypothesis space at the level of fields and
symmetries (for example, a Lagrangian). Experimental data, however, arrives
only after a lossy projection chain:

    Lagrangian -> amplitudes -> cross sections -> distributions
    -> detector + unfolding -> (y, Sigma)

Each arrow discards information (finite-order theory, unobserved degrees of
freedom, selection effects, detector response, correlated systematics). There
is no direct inversion from data back to a unique Lagrangian; inference must
proceed by selection among projected hypotheses under finite information.

We treat (y, Sigma) as an empirical communication channel and use MDL as a
rule for deciding how much structure is supported after correlations are
respected.


## MDL as Empirical Truncation

We score each model by:

    MDL = chi^2 + k log n

where k is the number of shape degrees of freedom and n is the number of bins.
This is an information-theoretic truncation rule: improvements in fit must pay
for added structure. We interpret k as an empirical lift depth of the
observable under its covariance.

One-sentence synthesis:

The Standard Model defines the space of allowed interactions, while minimal
description length applied to correlated data identifies the empirically
supported subspace for a given observable.


## Constant Atlas: Permissible Universal Constants

We define a "constant atlas" as an operational procedure that identifies which
dimensionless constants are empirically meaningful (identifiable) and supported
across domains.

1) Dimensionless-only candidate set.
Only dimensionless constants (or ratios) are searched over; dimensional
parameters are gauge-dependent on unit conventions.

2) Identifiability filter.
Given datasets D_j with covariance Sigma_j and a projection map f_j(theta),
compute local sensitivity (e.g., Fisher information):

    I(theta) = sum_j J_j^T Sigma_j^-1 J_j,   J_j = df_j/dtheta

Near-null directions of I(theta) correspond to constants that are not learnable
from the available channel and are not "permissible" in the empirical sense.

3) MDL selection.
Over nested constant subsets S (or model depth k), select the minimal set that
minimizes:

    MDL(S) = chi^2(theta_hat_S) + |S| log n

Report DeltaMDL margins as a strength indicator.

4) Cross-domain consistency.
To qualify as "universal," constants are treated as global parameters shared
across datasets, with domain-specific nuisance parameters. A constant is
supported when it is identifiable, reduces description length, and remains
consistent across domains within uncertainty.


## Minimal Worked Example (Toy Atlas)

Toy constants: theta = {alpha, mu, g_p} where mu = m_p/m_e.
Toy datasets: precision spectroscopy ratios with compact scaling laws.

Example scalings:

    f_opt ~ alpha^2 m_e c^2/h
    f_hfs ~ alpha^2 g_p mu^-1 m_e c^2/h

Taking a ratio cancels dimensional prefactors and leaves:

    f_hfs / f_opt ~ g_p mu^-1

This illustrates the atlas mechanics:

- alpha cancels in this ratio (non-identifiable from this dataset alone).
- mu and g_p are identifiable only up to degeneracy with a single ratio.
- adding an independent ratio breaks the degeneracy and allows MDL to select
  which constants are truly required.

The theory allows {alpha, mu, g_p}, but the empirical channel may only support
a lower-dimensional subspace unless additional datasets are included.

This toy example isolates the inference logic. The same atlas procedure
extends to SM electroweak/global fits and to cosmology, but the projection maps
are heavier.


## Empirical Illustration (ATLAS, 13 TeV, Full Covariance)

Implementation note: `13tev.py` is a frozen reference script. Do not modify it; create a new file for any experiments.

Using unfolded ATLAS diphoton spectra with published correlation matrices,
the complexity atlas reports:

- pT(γγ) selects Model B (one shape DOF) with a strong margin.
- N_jets is basis-sensitive: log basis favors Model C (curvature), while
  ordinal basis favors Model B with a moderate margin.

Conclusion: minimal shape complexity is observable-dependent under full
covariance, and representation choices matter for discrete observables.


## Pseudo-Data Harness (Structure Detectability)

To calibrate detectability under a fixed covariance channel, use the standalone
`pseudo_data_harness.py` script. It generates pseudo-data from a reference
shape plus controlled injections (tilt, curvature, line-like structure) and
reports MDL selection rates. This operationalizes the "structure detectability
engine" described in `CONTEXT.md:764` and `CONTEXT.md:1572`.

Implemented effective dimensionality detectability. This treats the log-basis
deformation parameters as scaling-exponent observables and scans their detection
thresholds under real covariance via `inject=dimension`. This direction is aligned
with the "effective dimensionality" roadmap in `CONTEXT.md:2706` through `CONTEXT.md:2805`
and the concrete test definition in `CONTEXT.md:3611` through `CONTEXT.md:3721`.

Effective dimensionality / dimensional flow detectability test:
- Model A: no dimension (normalization-only)
- Model B: fixed effective dimension (log-slope b)
- Model C: running dimension (log-curvature c)

Run the epsilon scan against the dimension injection:
`python pseudo_data_harness.py --inject dimension --scan --dim-b 1.0 --dim-c 0.0`
and repeat with nonzero `--dim-c` to force running dimension.

Record a "dimensional resolution atlas" table per observable + basis:
observable | basis   | eps50(B) | eps50(C) | interpretation
--------- | -------- | -------- | -------- | --------------
pT_yy     | log      | 0.12     | >1       | fixed dimension only
yAbs_yy   | linear   | 0.08     | 0.15     | running dimension detectable
N_j_30    | ordinal  | 0.20     | 0.22     | weak curvature support


## Related Approaches (Positioning)

Wolfram Physics Project. The Wolfram program explores rule space and studies
what causal structures can be generated by rewrite systems. Our method does not
generate or rank rules directly; it measures which emergent structures survive
projection through a noisy, correlated observation channel. In that sense, we
act as a post-projection filter over equivalence classes: causal invariance can
be read as an invariance of macroscopic observables under different micro-updates,
while MDL identifies which such invariances remain statistically supported. This
distinguishes rule richness from empirical support, consistent with the framing
in `CONTEXT.md:2706` through `CONTEXT.md:2805`.

Causal sets and CDT. Both causal set theory and causal dynamical triangulations
use scale-dependent diagnostics of geometry (for example, spectral dimension or
running dimension) rather than relying on narrow spectral spikes or single-event
signatures. The log-slope and curvature basis used here serves the same role: a
fixed scaling exponent corresponds to a single effective dimension, while a
curvature term corresponds to running dimension. This parallels the operational
focus in `CONTEXT.md:2706` through `CONTEXT.md:2805` and motivates why dimensional
flow is the primary falsifiable invariant in this pipeline, whereas line-like
structure is generally suppressed by binning and covariance.

Positioning statement. Allowed structures are not necessarily supported structures.
Rules, Lagrangians, and operator lists define the alphabet of possibilities; the
MDL-selected subspace is the sentence the data actually writes under projection.
Accordingly, this framework falsifies or supports emergent structural claims
after projection (scaling, locality, dimensional flow), but does not adjudicate
the metaphysical choice of underlying rule sets. It is a method for empirical
selection under information loss, not a generator of microscopic theories.


## Outlook

Pseudo-data validation:
Generate pseudo-measurements with known structure and the same covariance to
verify MDL recovers the true lift depth at realistic precision.

EFT/RG mapping:
Relate empirical lift depth to operator expansions by treating y_ref(x; theta)
as a template family and measuring when additional deformations are justified.
