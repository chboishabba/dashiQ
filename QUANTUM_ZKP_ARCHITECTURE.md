# Quantum ZKP Architecture

This note reframes the `dashiQ` quantum bridge in the `O/R/C/S/L/P/G/F` terms
already used elsewhere in the DASHI stack.

The goal is not to make DASHI itself "be a quantum computer" in one step.
The goal is to let DASHI host a governed quantum sub-regime with an explicit
seam between reversible evolution and promotable classical evidence.

## Core rule

Quantum evolution must stay separate from promotion.

Operationally:

- unitary evolution is reversible and remains latent
- measurement produces candidate classical evidence
- promotion is a later DASHI governance decision

So the minimal pipeline is:

```text
QState
-> UnitaryOp*
-> MeasurementOp
-> MeasurementRecord
-> PromotionPolicy
-> PromotionResult
```

## O: Organization

Use three layers:

- `dashiQ` core bridge
  - typed latent carrier
  - unitary / measurement split
  - decoder / witness / status surface
- quantum execution layer
  - state preparation
  - reversible updates
  - basis-aware measurement
- DASHI promotion layer
  - evidence thresholds
  - reproducibility policy
  - promotability status

`dashiQ` is therefore the supervising bridge, not the hardware target itself.

## R: Requirement

The actual requirement is:

- represent latent state without premature collapse
- support invertible evolution
- support explicit measurement as a separate operation
- preserve provenance for preparation, basis, and observation
- promote only measured/classical outputs into DASHI-style fact state

Anything that collapses quantum evolution directly into canonical state is the
wrong architecture.

## C: Code

The first code artifact should expose:

- `QState`
- `UnitaryOp`
- `MeasurementOp`
- `MeasurementRecord`
- `PromotionPolicy`
- `PromotionResult`
- `Observable`

And one executor:

- `run_quantum_pipeline(...)`

The first implementation can stay toy-sized, but it needs the seam to be real.

## S: State

Keep three state regimes distinct.

### Latent quantum state

- amplitude carrier
- reversible
- non-canonical
- branchable

### Observational state

- measured outcomes
- probabilities / histograms
- expectation summaries
- provenance bundle

### Promoted state

- validated classical summaries
- accepted downstream facts
- accepted optimization or control outputs

Only the last one should behave like ordinary promoted DASHI state.

## L: Lattice

Do not order raw amplitudes by truth.

The useful lattice is over admissibility and evidence:

```text
ill_typed
< prepared
< evolved
< measured
< validated
< promoted
```

And separately:

```text
simulation_only
< validated_simulation
< hardware_observed
< replicated_hardware
```

## P: Proposal

A quantum proposal packet should contain:

- objective
- preparation rule
- circuit / unitary family
- measurement schema
- observable target
- shot budget
- backend or simulator tag
- acceptance criterion
- promotion criterion

That turns "run a circuit" into a typed DASHI action rather than an opaque call.

## G: Governance

Governance decides:

- which backends are trusted
- whether simulation-only evidence is promotable
- how many shots are sufficient
- whether postselection is allowed
- whether mitigation is admissible
- what reproducibility means for a given regime

So DASHI governs epistemic status, not the internal amplitudes themselves.

## F: Gap

The natural gap is promotability distance from measurement output to accepted
classical fact.

The first version can score:

- validity of the quantum artifact
- probability mass / confidence concentration
- reproducibility metadata
- utility or compressive value

This is intentionally narrower than a full physical error budget.

## Immediate implementation consequence

The first bridge module should:

- keep `UnitaryOp` and `MeasurementOp` disjoint
- treat `MeasurementRecord` as the first classical object
- make promotion policy explicit
- emit a tiny witness/status surface so the repo can distinguish:
  - exact semantic claims
  - approximate simulator claims
  - heuristic observable claims

That is the smallest honest "quantum inside DASHI" implementation target.

## Current implementation state

This repo now has a partial realization of that split:

- `computer_v1.py`
  - first bridge prototype
  - direct seam exploration
- `computer_v2.py`
  - typed multi-carrier runtime
  - dispatches by `QUBIT`, `QUTRIT`, and `TRIALITY`
  - selection is now first-class for qutrit (projection family scoring with
    entropy-gap/coherence weights; motif path can prefer dashifine defaults or
    curated weights and otherwise fall back to an Agda-inspired ternary
    coarse/tail MDL weighting over `Vec Trit 3`, now with an extra
    coarse-pattern code penalty and a default cyclic coarse-tail dynamics
    ensemble) and triality
    (explicit MDL-style pair scoring over signal/stability/symmetry terms;
    configurable weights, optional `mdl` preset from norm dispersion; terms
    recorded in witness)

In `O/R/C/S/L/P/G/F` terms, the main unresolved item has moved:

- `O/C/S/L` are now substantially in place for the first carriers
- `P/G/F` pressure remains inside typed carriers:
  - `qutrit_motif27` now enters a five-candidate additive-comparison program:
    static prior, cyclic dynamics baseline, larger-latent tail dynamics,
    deterministic ensemble, projection-covariant generator, triality-coupled
    generator, and an experimental CCR/Weyl-inspired path
  - the current `qg_dynamics` path remains the default baseline, with witness
    comparison now exposing the other candidates side by side; the policy
    requires beating baseline on projection score and entropy-gap, and being
    non-experimental
  - the current governance rule is conservative: a candidate must beat
    `qg_dynamics` on both projection score and entropy-gap, and not be
    experimental, before baseline replacement is considered
  - MDL-grade `F` is not yet implemented; current gaps are carrier-specific
    heuristics using selection + entropy/correlation

So the next useful work is not broader architecture. It is to improve the
carrier-native semantics inside the typed runtime already present.
