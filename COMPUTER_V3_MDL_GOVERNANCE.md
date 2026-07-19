# Computer v3: MDL-Governed Promotion

`computer_v3.py` closes the next governance seam over the existing typed runtime.
It does not replace `computer_v2.py`.

## Layering

```text
computer_v2
  carrier-native state / evolution / selection / measurement / candidate policy

computer_v3
  carrier-appropriate null model
  -> structured-model code length
  -> evidence gain
  -> fail-closed DASHI promotion
```

The full pipeline is:

```text
QState
-> UnitaryOp*
-> carrier-native MeasurementRecord
-> v2 PromotionResult (candidate evidence)
-> MDLEvidenceLedger
-> GovernedPromotionResult
```

Raw amplitudes remain latent and non-canonical. The common `F` surface is defined
only after measurement:

```text
F = minimum_required_evidence_gain - observed_evidence_gain
```

Therefore:

- `F <= 0` means the measured structured model pays for its own code length;
- `F > 0` means promotion remains blocked;
- v3 promotion additionally requires the carrier-native v2 policy to accept.

## Carrier-specific code models

### Qubit / CHSH

- null: classical CHSH bound `|S| <= 2`
- evidence: excess beyond the classical bound relative to the recorded error scale
- model cost: one effect-size parameter plus a named measurement-family cost

### Qutrit and 27 -> 9 motif paths

- null: uniform categorical distribution over measured support
- structured data cost: Shannon code `shots * H(p)`
- model cost: BIC-style simplex-coordinate cost
- selection cost: `log(number of searched projections)`

This means qutrit promotion no longer rewards entropy gap without paying for the
projection search and the dimensionality of the fitted simplex.

### Triality

- null: zero selected-pair correlation
- evidence: selected correlation relative to its recorded stability/error scale
- model cost:
  - the v2 intrinsic signal/stability/symmetry `mdl_cost`
  - `log(number of candidate pairs)`
  - one effect-size parameter

The selection cost is therefore carried through to promotion rather than hidden
behind the selected pair.

## Witness discipline

The v3 witness:

- preserves the complete v2 witness;
- changes the schema to `dashiQ.quantum_bridge.v3`;
- retains the v2 decision as `candidate_promotion`;
- adds a fully serializable `mdl_evidence` ledger;
- replaces final `promotion` with the fail-closed governed decision;
- distinguishes promoted classical evidence from candidate/blocked evidence.

## O, R, C, S, L, P, G, F

| Axis | Computer-v3 realization |
|---|---|
| O | `computer_v2` executes carrier semantics; `computer_v3` governs promotion. |
| R | Promotion must require carrier acceptance and positive code-length evidence. |
| C | `MDLEvidenceLedger`, `GovernedPromotionResult`, carrier ledgers, governed runner. |
| S | Latent `QState` stays non-canonical; only measurement records enter the ledger. |
| L | latent -> evolved -> measured -> candidate -> MDL-sufficient -> promoted. |
| P | The carrier policy proposes a classical evidence packet. |
| G | Candidate acceptance and MDL sufficiency are conjunctive, fail-closed gates. |
| F | `minimum_gain - evidence_gain`, evaluated only on measured evidence. |

## Validation

`test_computer_v3.py` uses synthetic records to test the governance layer without
requiring optional preparation modules. It checks:

- strong CHSH excess can pay its model cost;
- classical-bound CHSH remains blocked;
- a structured qutrit distribution can beat a uniform null;
- a uniform qutrit distribution cannot pay its model cost;
- triality pair-selection and intrinsic MDL costs are retained;
- final promotion requires both the v2 candidate gate and MDL sufficiency.

Run:

```bash
python -m unittest -v test_computer_v3.py
python computer_v3.py
```

The second command uses the current real v2 preparation paths and prints the
candidate decision, evidence gain, promotability gap, and final governed result
for each carrier.

## Boundaries

This is an MDL/BIC evidence bridge, not a derivation of the Born rule and not a
hardware compiler. The normal-error approximations for expectation-like
observables are explicit assumptions in each witness ledger. A later version can
replace those summary likelihoods with exact shot-count likelihoods when v2
records raw outcome counts for all carriers.
