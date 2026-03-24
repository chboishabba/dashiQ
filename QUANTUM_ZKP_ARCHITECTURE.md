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
