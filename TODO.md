TODO

- No open items for Test III scans.
- HL-LHC prediction program (di-Higgs/self-coupling): compute permissible/
  discoverable/aliased regions for κλ using current vs HL-LHC channel models,
  and record κλ ranges per region.
- Physics targets: pick a first direction from `PHYSICS_TARGETS.md` and define
  latent structure class, observation channel, invariants, and a falsifiable
  prediction.
- Path C cross-check: run the same log-basis MDL test on a second observable
  (e.g., `N_j_30` with `N_j_30_corr`) and record the best model by MDL.
- Projection–Invariance paper spine: draft the Definitions → Theorem → Proof →
  Falsifier section and insert "Why non-detection is expected".
- Grokking ML theorem: write the valuation-resolution/identifiability statement
  parallel to Projection–Invariance and define the minimal falsifiable test for
  Welch modular addition (choose NTK vs Hessian vs gradient covariance probe).
- Quantum bridge / internalization:
  - Bridge note landed: `QUANTUM_BRIDGE_INTERFACE.md`.
  - Inventory `temp_dashifine_quantum/` by role:
    - pure simulation
    - diagnostics / plotting
    - candidate bridge utilities
    - obsolete one-off probes
  - Define a minimal Python-facing interface for the bridge:
    - `State`
    - `step`
    - `measure`
    - `observable`
    - `reconstruct` or `infer`
  - Implement the first actual `dashiQ` interface module from the bridge note:
    - landed initial skeleton in `quantum_bridge.py`
    - next: widen from toy 2D carrier to the first real `J`/qutrit-facing
      bridge carrier
    - next: separate exact projector semantics from sampled measurement
    - next: add proposal/governance packet types instead of only the promotion
      policy object
  - Implement one toy bridge simulator where deterministic latent dynamics plus
    coarse measurement can produce quantum-like unpredictability at the
    observation layer:
    - first toy version now exists as the `Rotation2D` +
      `ComputationalBasisMeasurement` path in `quantum_bridge.py`
    - first CHSH-oriented machine instance now exists in `computer_v1.py`
    - direct `dashifine` imports now used for the stable seam:
      - `lattice_chsh.prepare_two_qubit_state("ideal_bell")`
      - `triality_stack.R`
      - `chsh_harness.tsirelson_angles`
      - `chsh_harness.chsh_S`
      - `chsh_harness.two_qubit_from_two_local_planes`
    - default prep now uses the lattice-frame path via
      `build_single_leg_open` + `extract_wall_qubit_frame`
    - extension prep modes now exist for:
      - `triality_frames`
      - `qutrit_planes`
    - `triality_frames` now has an explicit witness rule:
      near-zero mode rank `0`, select pair by max absolute pair correlation
    - `qutrit_planes` now has a qutrit-native loop:
      - 9-outcome basis distribution
      - entropy-gap observable
      - qutrit-specific promotion policy
    - `computer_v2.py` now exists as the typed carrier-dispatch layer:
      - `CarrierType = QUBIT | QUTRIT | TRIALITY`
      - carrier-specific runtime registry / dispatch
      - typed promotability gaps
      - real `qutrit_motif27` path using `map_27_to_H3x3.coarse9_from_weights27`
      - witness fields now standardized around a shared v2 schema:
        `witness_schema`, `source_semantics`, `measurement_kind`,
        `carrier`, `evolution`, `measurement`, `observable`, `promotion`
    - `computer_v1.py` witness is now v2-compatible at the field level:
      keep using it as the prototype/seam file, not the place for new dispatch
    - next for `computer_v2.py`:
      - replace the current triplet-basis motif seed with a less ad hoc
        qutrit/triplet preparation path from `dashifine/newtest`
      - decide how much of `computer_v1.py` to absorb into `computer_v2.py`
        without losing the useful seam-by-seam prototype clarity
    - next for `triality_frames`: move beyond the current max-correlation rule to
      a more physically motivated multi-leg selection or mode-selection
      functional
    - next for `qutrit_planes`: move beyond the current basis/entropy observable
      to a richer qutrit-native observable family or 27→9 motif-facing path
  - Borrow the right parts of `FRACDASH` into the first simulator:
    - explicit decoder/readout layer
    - exact vs approximate claim surface
    - minimal witness/status record for carrier / evolution / projection /
      observable semantics
    - first minimal witness/status surface now exists; next step is to make it
      configurable per carrier and per measurement family
  - Keep the p-adic route clearly separated into:
    - formal/simulator support now
    - hardware/execution claims later only if a real compilation path exists
  - Only after the simulator/interface is stable, specify the later
    "DASHI on a quantum computer" compilation target (gate set, state encoding,
    and admissible operations).
- Dark-sector portal lifetime proxy: decide which trajectory datasets and arrow
  coordinate to use for cone-residence measurements.
- Dark-sector portal lifetime proxy: implement cone slack, arrow accumulation,
  and boundary-exit time metrics on delta-cone trajectories.
- Dark-sector portal lifetime proxy: produce a table of proxy statistics per
  observable/label and a short interpretation for displaced-vertex signatures.
- Dark-sector portal lifetime proxy: define a minimal calibration plan to map
  proxy units to collider scales (even if only relative ordering at first).
