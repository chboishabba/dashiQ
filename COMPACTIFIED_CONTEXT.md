# Compactified Context

Last updated: 2026-03-24

## Current focus
- The repo centers on projection -> covariance -> MDL as a selection principle.
- Full-covariance ATLAS results are treated as minimal shape complexity tests
  when no SM baseline is present.

## New intent (Dark-sector portal lifetime proxy)
- Use delta-cone / arrow-geometry machinery to define a **lifetime proxy** for
  hidden-sector intermediates relevant to displaced-vertex signatures.
- Lifetime is interpreted as **cone-residence time** along the arrow/depth axis,
  not as an intrinsic particle parameter.
- Planned observables: cone slack, arrow accumulation, boundary-exit time.

## Status
- Documented Path C result for `pT_yy` (Model B wins under full covariance).
- Projection–Invariance Theorem is locked with operational corollary and a draft
  paper-spine section ("Why non-detection is expected").
- Grokking is formalized as valuation-resolution / identifiability transition
  (Welch modular-addition), with a minimal falsifiable test.
- Noted related repo-comparison chat IDs from `../CHAT_ID_INDEX.md`.
- Documentation and TODO updated; no code changes yet.

## New intent (Quantum bridge / internalization)
- `all_code58.txt` was copied in from `../dashi_agda/` so the current Agda
  quantum/formalism snapshot is locally available in this repo too.
- `QUANTUM_BRIDGE_INTERFACE.md` now exists as the concrete bridge note:
  - defines the `state -> invertible evolution -> measurement/projection ->
    observable` interface in implementation terms
  - inventories which `dashifine/newtest` modules map cleanly onto each seam
  - isolates `J` / quarter-turn as the main reusable local complex-structure
    bridge object
- `QUANTUM_ZKP_ARCHITECTURE.md` now records the same bridge in the
  `O/R/C/S/L/P/G/F` frame:
  - latent quantum state remains non-canonical
  - measurement is the first classical evidence seam
  - promotion is a later governance step
- `quantum_bridge.py` now provides the first minimal Python skeleton for:
  - `QState`
  - `UnitaryOp`
  - `MeasurementOp`
  - `MeasurementRecord`
  - `PromotionPolicy`
  - `PromotionResult`
  - `run_quantum_pipeline(...)`
  - `computer_v1.py` now provides the first CHSH-oriented machine instance:
  - Bell-state latent carrier
  - `J`-style reversible evolution hook
  - multi-shot CHSH measurement record with variance
  - promotion decision and FRACDASH-style witness
  - simple promotability gap `F`
  - now prefers real `dashifine/newtest` imports for:
    - `lattice_chsh.prepare_two_qubit_state("ideal_bell")`
    - `triality_stack.R`
    - `chsh_harness.tsirelson_angles`
    - `chsh_harness.chsh_S`
  - default prep mode is now `local_planes` via:
    - superseded as the default by `lattice_frames`
  - default prep mode is now `lattice_frames` via:
    - `lattice_chsh.build_single_leg_open`
    - `lattice_chsh.extract_wall_qubit_frame`
    - `chsh_harness.two_qubit_from_two_local_planes`
  - `local_planes` and `ideal_bell` remain available as explicit comparison
    modes
  - two new extension prep modes now exist in `computer_v1.py`:
    - `triality_frames`
      - `triality_stack.build_triality_stack_H`
      - `triality_stack.eigh_sorted_by_abs`
      - `chsh_harness.extract_local_plane_basis_at_wall`
      - `chsh_harness.two_qubit_from_two_local_planes`
      - now a real triality-native loop:
        - evaluate all leg pairs from the extracted near-zero-mode wall planes
        - select by max absolute pair correlation
        - promote on pair-correlation stability
      - witness records the selection rule and selected pair
    - `qutrit_planes`
      - `ternary_hilbert.embed_qubit_plane`
      - `embed_chsh_ternary.bell_phi_plus`
      - witness now includes the qutrit-embedded CHSH expectation via
        `embed_chsh_ternary.expectation_in_embedded_CHSH`
  - current status:
    - all three richer prep modes (`lattice_frames`, `triality_frames`,
      `qutrit_planes`) execute and preserve the CHSH bridge path
    - the qutrit-facing mode is now a real qutrit-state path in `computer_v1`:
      - two-qutrit embedded latent state (9D)
      - qutrit basis-distribution measurement
      - entropy-gap observable
      - qutrit-specific promotion rule
      - embedded CHSH retained only as reference metadata in the witness
  - `computer_v2.py` now provides the next layer up:
    - explicit `CarrierType = QUBIT | QUTRIT | TRIALITY`
    - typed dispatch for measurement / promotion / witness / gap
    - carrier-specific pipelines instead of manual branching
    - a richer qutrit `qutrit_motif27` path:
      - 27-state latent carrier
      - 27 -> 9 motif coarse-graining via
        `dashifine/newtest/map_27_to_H3x3.py`
      - current prep is expressed through explicit triplet-basis components via
        `triplet_ket` + `mix_over_27`, not a raw weight-vector shortcut
      - motif-entropy-gap observable
      - qutrit-specific promotion under motif semantics
    - v2 witnesses now use a more explicit shared schema:
      - `witness_schema`
      - `source_semantics`
      - `measurement_kind`
      - `carrier`
      - `evolution`
      - `measurement`
      - `observable`
      - `promotion`
    - `computer_v1.py` now emits a v2-compatible witness shape at the field
      level, but remains the earlier bridge prototype
    - `computer_v2.py` is the first carrier-dispatched machine core and should
      be treated as the default place for new carrier/runtime growth
- The immediate quantum priority is now explicitly:
  1. quantum simulation / internalization / bridge to DASHI
  2. only then "DASHI on a quantum computer" as a later compilation/execution
     target
- The current Agda spine worth treating as canonical source structure is:
  - `DASHI.Algebra.QuantumInterface`: latent state + invertible step +
    measurement split
  - `DASHI.Algebra.Quantum.Measurement`: collapse as non-invertible projection
  - `DASHI.Algebra.Quantum.Unitary`: unitary/invertible evolution
  - `DASHI.Algebra.Quantum.CCRFromProjection`: projection -> CCR/Weyl bridge
  - `DASHI.Quantum.Stone`: continuous-time / Stone bundle layer
- Repo ownership split is now sharper:
  - `dashiQ`: owns the bridge note, internal formalism, and simulator-facing
    interface
  - `dashifine` and mirrored `dashitest/dashifine`: own the current
    quantum-faithful classical experiments (CHSH, qutrit embedding, SSH /
    lattice utilities, quantum-defect demos)
  - `FRACDASH`: contributes bridge-correctness and executable-witness
    discipline, not the quantum carrier/measurement interface itself
- Language constraint:
  - current `dashifine` / `dashitest` quantum utilities are classical
    simulation / lattice-realization tools, not quantum hardware or quantum
    advantage work
  - `FRACDASH` should be read as a semantics/compilation-pattern donor:
    source -> executable IR -> target -> decoder/status, useful for `dashiQ`
    witness/reporting and quotient discipline
- Local archive cross-check (2026-03-24, source=`db`):
  - `P-adic quantum systems`
    - online UUID: `6919bf75-af7c-8324-b2be-bfc2306d8208`
    - canonical thread ID: `c5adc26f07706a65a5da6043eb91810f3041c9c0`
    - decision pulled: p-adic quantum systems are a real formal family, but
      they are not the same thing as ordinary qubits/qutrits and are not a
      ready-made hardware path; near-term value here is simulator/formalism
      design, not hardware claims.
  - `Quarter turn in quantum`
    - online UUID: `690e6469-9508-8320-86b4-669fe11d6245`
    - canonical thread ID: `17bde1e6b2b7d785009b992bfaa1c4d74298dcb8`
    - decision pulled: the useful reusable object is the quarter-turn operator
      `J` as a local complex-structure / phase-rotation generator; this belongs
      in the bridge/interface layer and can connect the current lattice demos
      to the Agda unitary/measurement split.
  - `Math Prof Outreach Stage`
    - online UUID: `69aa52b4-6f7c-839f-aa7f-d120ffe0c1ad`
    - canonical thread ID: `decf9e3cde5ccdec0c51ad8aab15999201503998`
    - decision pulled: wave-facing bridge language already exists in the
      broader DASHI closure story, but wave/module lift is still not the same
      as finished physics closure; so the bridge note should treat wave/Stone/
      CCR seams as extension points, not as already-closed physics.
