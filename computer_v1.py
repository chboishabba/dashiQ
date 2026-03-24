"""First CHSH-oriented quantum computer bridge for dashiQ.

This module keeps the critical seam explicit:

- latent quantum state remains non-canonical
- reversible evolution is separate from measurement
- measurement produces candidate classical evidence
- promotion is a later governance decision
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import sys

    _DASHIFINE_NEWTEST = "/home/c/Documents/code/dashifine/newtest"
    if _DASHIFINE_NEWTEST not in sys.path:
        sys.path.insert(0, _DASHIFINE_NEWTEST)
    import chsh_harness as _dashifine_chsh_harness
    import embed_chsh_ternary as _dashifine_embed_chsh_ternary
    import lattice_chsh as _dashifine_lattice_chsh
    import map_27_to_H3x3 as _dashifine_map_27_to_H3x3
    import ternary_hilbert as _dashifine_ternary_hilbert
    import triality_stack as _dashifine_triality_stack
except ImportError:
    _dashifine_chsh_harness = None
    _dashifine_embed_chsh_ternary = None
    _dashifine_lattice_chsh = None
    _dashifine_map_27_to_H3x3 = None
    _dashifine_ternary_hilbert = None
    _dashifine_triality_stack = None


def _normalize(vector: np.ndarray) -> np.ndarray:
    array = np.asarray(vector, dtype=complex)
    norm = np.linalg.norm(array)
    if norm <= 0.0:
        raise ValueError("quantum state must have nonzero norm")
    return array / norm


@dataclass(frozen=True)
class QState:
    """Latent, non-canonical state carrier."""

    vector: np.ndarray
    basis: str = "computational"
    provenance: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vector", _normalize(self.vector))
        if self.provenance is None:
            object.__setattr__(self, "provenance", {})

    @property
    def dimension(self) -> int:
        return int(self.vector.shape[0])


@dataclass(frozen=True)
class PreparationSpec:
    mode: str
    source: str
    params: dict[str, Any] | None = None
    carrier: str = "qubit"


class UnitaryOp:
    """Exact reversible update on latent state."""

    def __init__(self, unitary: np.ndarray, name: str = "U"):
        matrix = np.asarray(unitary, dtype=complex)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("unitary must be a square matrix")
        self.U = matrix
        self.U_inv = matrix.conj().T
        self.name = name

    def step(self, state: QState) -> QState:
        provenance = dict(state.provenance)
        provenance["last_unitary"] = self.name
        return QState(self.U @ state.vector, basis=state.basis, provenance=provenance)

    def inv(self, state: QState) -> QState:
        provenance = dict(state.provenance)
        provenance["last_unitary_inv"] = self.name
        return QState(self.U_inv @ state.vector, basis=state.basis, provenance=provenance)


class MeasurementOp:
    """Basis-aware measurement family with explicit coarse projection."""

    def __init__(self, observables: dict[str, np.ndarray], name: str = "measurement"):
        self.observables = {
            key: np.asarray(value, dtype=complex) for key, value in observables.items()
        }
        self.name = name

    def project(self, state: QState) -> QState:
        # Minimal idempotent coarse projection for v1: normalize and retain basis.
        provenance = dict(state.provenance)
        provenance["projected_by"] = self.name
        return QState(state.vector, basis=state.basis, provenance=provenance)

    def measure_once(self, state: QState) -> dict[str, float]:
        bra = state.vector.conj().T
        return {
            name: float(np.real(bra @ op @ state.vector))
            for name, op in self.observables.items()
        }

    def measure(
        self,
        state: QState,
        shots: int = 100,
        rng: np.random.Generator | None = None,
        noise_scale: float = 0.0,
    ) -> tuple[dict[str, float], list[dict[str, float]]]:
        if shots <= 0:
            raise ValueError("shots must be positive")
        generator = rng or np.random.default_rng()
        exact = self.measure_once(state)
        if noise_scale < 0.0:
            raise ValueError("noise_scale must be non-negative")

        samples: list[dict[str, float]] = []
        for _ in range(shots):
            sample: dict[str, float] = {}
            for key, value in exact.items():
                jitter = float(generator.normal(0.0, noise_scale)) if noise_scale else 0.0
                sample[key] = float(np.clip(value + jitter, -1.0, 1.0))
            samples.append(sample)

        mean = {
            key: float(np.mean([sample[key] for sample in samples])) for key in exact
        }
        return mean, samples


@dataclass(frozen=True)
class MeasurementRecord:
    """Classical evidence object emitted by the bridge."""

    datum: dict[str, float]
    projected_state: QState
    observable: float
    shots: int
    variance: float
    measurement_kind: str = "expectation"


@dataclass(frozen=True)
class PromotionResult:
    accepted: bool
    reason: str
    datum: dict[str, float]


class PromotionPolicy:
    """Governance and promotability rule."""

    def __init__(self, s_threshold: float = 2.0, var_threshold: float = 0.05):
        self.s_threshold = s_threshold
        self.var_threshold = var_threshold

    def decide(self, record: MeasurementRecord) -> PromotionResult:
        if record.variance > self.var_threshold:
            return PromotionResult(False, "high_variance", record.datum)
        if abs(record.observable) > self.s_threshold:
            return PromotionResult(True, "nonlocal_signal", record.datum)
        return PromotionResult(False, "classical_or_weak_signal", record.datum)


class QutritPromotionPolicy:
    """Qutrit-native promotion rule based on entropy stability and non-uniformity."""

    def __init__(self, entropy_var_threshold: float = 0.02, min_entropy_gap: float = 0.10):
        self.entropy_var_threshold = entropy_var_threshold
        self.min_entropy_gap = min_entropy_gap

    def decide(self, record: MeasurementRecord) -> PromotionResult:
        if record.variance > self.entropy_var_threshold:
            return PromotionResult(False, "high_entropy_variance", record.datum)
        if record.observable > self.min_entropy_gap:
            return PromotionResult(True, "structured_qutrit_distribution", record.datum)
        return PromotionResult(False, "near_uniform_qutrit_distribution", record.datum)


class TrialityPromotionPolicy:
    """Triality-native promotion rule on selected pair correlation."""

    def __init__(self, corr_threshold: float = 0.5, var_threshold: float = 0.05):
        self.corr_threshold = corr_threshold
        self.var_threshold = var_threshold

    def decide(self, record: MeasurementRecord) -> PromotionResult:
        if record.variance > self.var_threshold:
            return PromotionResult(False, "unstable_pair", record.datum)
        if abs(record.observable) < self.corr_threshold:
            return PromotionResult(False, "weak_signal", record.datum)
        pair = record.datum.get("selected_pair", [-1, -1])
        return PromotionResult(
            True,
            f"selected_pair_{tuple(pair)}",
            record.datum,
        )


def pauli_x() -> np.ndarray:
    return np.array([[0, 1], [1, 0]], dtype=complex)


def pauli_z() -> np.ndarray:
    return np.array([[1, 0], [0, -1]], dtype=complex)


def kron(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.kron(a, b)


def chsh_operators() -> dict[str, np.ndarray]:
    a0 = pauli_z()
    a1 = pauli_x()
    b0 = (pauli_z() + pauli_x()) / np.sqrt(2.0)
    b1 = (pauli_z() - pauli_x()) / np.sqrt(2.0)
    return {
        "A0B0": kron(a0, b0),
        "A0B1": kron(a0, b1),
        "A1B0": kron(a1, b0),
        "A1B1": kron(a1, b1),
    }


def tsirelson_angles() -> tuple[float, float, float, float]:
    if _dashifine_chsh_harness is not None:
        return _dashifine_chsh_harness.tsirelson_angles()
    return (0.0, 0.5 * np.pi, 0.25 * np.pi, -0.25 * np.pi)


def chsh_S(data: dict[str, float]) -> float:
    return data["A0B0"] + data["A0B1"] + data["A1B0"] - data["A1B1"]


def chsh_S_from_state(
    psi: np.ndarray, angles: tuple[float, float, float, float] | None = None
) -> float:
    if angles is None:
        angles = tsirelson_angles()
    a, ap, b, bp = angles
    if _dashifine_chsh_harness is not None:
        return _dashifine_chsh_harness.chsh_S(psi, a, ap, b, bp)
    observables = chsh_operators()
    bra = psi.conj().T
    data = {
        name: float(np.real(bra @ op @ psi))
        for name, op in observables.items()
    }
    return chsh_S(data)


class QuantumSys:
    """Latent state + reversible evolution + explicit measurement."""

    def __init__(self, state: QState, evolution: UnitaryOp, measurement: MeasurementOp):
        self.state = state
        self.evolution = evolution
        self.measurement = measurement

    def evolve(self, steps: int = 1) -> None:
        if steps < 0:
            raise ValueError("steps must be non-negative")
        for _ in range(steps):
            self.state = self.evolution.step(self.state)

    def run_measurement(
        self,
        shots: int = 100,
        rng: np.random.Generator | None = None,
        noise_scale: float = 0.0,
    ) -> MeasurementRecord:
        projected = self.measurement.project(self.state)
        mean, samples = self.measurement.measure(
            self.state,
            shots=shots,
            rng=rng,
            noise_scale=noise_scale,
        )
        s_value = chsh_S(mean)
        s_samples = [chsh_S(sample) for sample in samples]
        variance = float(np.var(s_samples))
        return MeasurementRecord(
            datum=mean,
            projected_state=projected,
            observable=s_value,
            shots=shots,
            variance=variance,
            measurement_kind="chsh_expectation",
        )


def _shannon_entropy(probabilities: np.ndarray) -> float:
    probs = probabilities[probabilities > 0.0]
    if probs.size == 0:
        return 0.0
    return float(-np.sum(probs * np.log(probs)))


def _qutrit_basis_labels() -> list[str]:
    return [f"{i}{j}" for i in range(3) for j in range(3)]


def qutrit_native_measurement(
    state: QState,
    shots: int = 100,
    rng: np.random.Generator | None = None,
) -> MeasurementRecord:
    if state.dimension != 9:
        raise ValueError("qutrit native measurement expects a 9D two-qutrit state")
    if shots <= 0:
        raise ValueError("shots must be positive")
    generator = rng or np.random.default_rng()
    probabilities = np.abs(state.vector) ** 2
    probabilities = probabilities / probabilities.sum()
    labels = _qutrit_basis_labels()
    samples = generator.choice(len(labels), size=shots, p=probabilities)
    counts = np.bincount(samples, minlength=len(labels))
    frequencies = counts / float(shots)
    datum = {label: float(freq) for label, freq in zip(labels, frequencies)}
    sample_entropies = []
    for index in samples:
        one_hot = np.zeros(len(labels), dtype=float)
        one_hot[index] = 1.0
        sample_entropies.append(_shannon_entropy(one_hot))
    empirical_entropy = _shannon_entropy(frequencies)
    max_entropy = float(np.log(len(labels)))
    entropy_gap = max_entropy - empirical_entropy
    variance = float(np.var(sample_entropies + [empirical_entropy]))
    winner = int(np.argmax(frequencies))
    collapsed = np.zeros(len(labels), dtype=complex)
    collapsed[winner] = 1.0 + 0.0j
    projected_state = QState(
        collapsed,
        basis="qutrit_computational",
        provenance={**state.provenance, "projected_by": "qutrit_basis_measurement"},
    )
    return MeasurementRecord(
        datum=datum,
        projected_state=projected_state,
        observable=entropy_gap,
        shots=shots,
        variance=variance,
        measurement_kind="qutrit_distribution_entropy_gap",
    )


def _triality_pair_labels() -> tuple[tuple[int, int], ...]:
    return ((0, 1), (0, 2), (1, 2))


def triality_select_pair(pair_scores: dict[tuple[int, int], float]) -> tuple[tuple[int, int], float]:
    pair = max(pair_scores, key=lambda key: abs(pair_scores[key]))
    return pair, float(pair_scores[pair])


def triality_native_measurement(
    state: QState,
    preparation: PreparationSpec,
    shots: int = 100,
    rng: np.random.Generator | None = None,
    noise_scale: float = 0.0,
) -> MeasurementRecord:
    params = preparation.params or {}
    planes = params.get("leg_plane_vectors")
    if planes is None:
        raise ValueError("triality measurement requires leg_plane_vectors")
    generator = rng or np.random.default_rng()
    samples: list[dict[tuple[int, int], float]] = []
    for _ in range(shots):
        sample: dict[tuple[int, int], float] = {}
        for pair in _triality_pair_labels():
            base = float(abs(np.vdot(np.asarray(planes[pair[0]], complex), np.asarray(planes[pair[1]], complex))))
            jitter = float(generator.normal(0.0, noise_scale)) if noise_scale else 0.0
            sample[pair] = float(np.clip(base + jitter, 0.0, 1.0))
        samples.append(sample)
    mean_scores = {
        pair: float(np.mean([sample[pair] for sample in samples]))
        for pair in _triality_pair_labels()
    }
    selected_pair, correlation = triality_select_pair(mean_scores)
    variance = float(np.var([sample[selected_pair] for sample in samples]))
    projected_state = QState(
        state.vector,
        basis=state.basis,
        provenance={**state.provenance, "projected_by": "triality_pair_measurement"},
    )
    datum = {
        "selected_pair": list(selected_pair),
        "pair_scores": {f"{i}{j}": value for (i, j), value in mean_scores.items()},
    }
    return MeasurementRecord(
        datum=datum,
        projected_state=projected_state,
        observable=correlation,
        shots=shots,
        variance=variance,
        measurement_kind="triality_pair_correlation",
    )


def build_witness(
    system: QuantumSys, record: MeasurementRecord, preparation: PreparationSpec
) -> dict[str, Any]:
    claim_status = (
        "exact_evolution_observable" if record.variance < 1e-6 else "statistical_observable"
    )
    source_semantics = (
        "two_qutrit_embedded_state"
        if preparation.carrier == "qutrit"
        else ("triality_wall_mode_pair" if preparation.carrier == "triality" else "2-qubit Hilbert state")
    )
    carrier_name = preparation.mode
    prep_metadata = {
        "source": preparation.source,
        "mode": preparation.mode,
        "params": preparation.params,
    }
    witness = {
        "witness_schema": "dashiQ.quantum_bridge.v2_compatible",
        "source_semantics": source_semantics,
        "carrier": preparation.carrier,
        "carrier_name": carrier_name,
        "prep_metadata": prep_metadata,
        "evolution": {
            "type": system.evolution.name,
            "exact": True,
            "invertible": True,
            "source": (
                "dashifine.newtest.triality_stack.R"
                if _dashifine_triality_stack is not None
                else "local_fallback"
            ),
        },
        "measurement": {
            "type": (
                "triality_pair_measurement"
                if preparation.carrier == "triality"
                else system.measurement.name
            ),
            "projection": "idempotent_normalization",
            "quotient": True,
            "source": (
                "triality_native_measurement"
                if preparation.carrier == "triality"
                else (
                    "dashifine.newtest.chsh_harness.chsh_S"
                    if _dashifine_chsh_harness is not None
                    else "local_fallback"
                )
            ),
        },
        "observable": {
            "name": (
                "entropy_gap_over_qutrit_basis"
                if preparation.carrier == "qutrit"
                else ("pair_correlation" if preparation.carrier == "triality" else "CHSH_S")
            ),
            "value": record.observable,
            "variance": record.variance,
            "shots": record.shots,
            "bounds": (
                {"min": 0.0, "max": float(np.log(9.0))}
                if preparation.carrier == "qutrit"
                else (
                    {"min": 0.0, "max": 1.0}
                    if preparation.carrier == "triality"
                    else {"classical": 2.0, "quantum": float(2.0 * np.sqrt(2.0))}
                )
            ),
        },
        "measurement_kind": record.measurement_kind,
        "promotion": None,
        "claim_status": claim_status,
    }
    if preparation.mode == "triality_frames":
        witness["prep_metadata"]["selection_rule"] = (
            "argmax_abs_pair_correlation_over_near_zero_mode_rank_0_leg_planes"
        )
        witness["selection"] = {
            "pair": record.datum.get("selected_pair"),
            "pair_scores": record.datum.get("pair_scores"),
            "rule": "max_abs_correlation",
        }
    if (
        preparation.mode == "qutrit_planes"
        and _dashifine_embed_chsh_ternary is not None
        and _dashifine_ternary_hilbert is not None
    ):
        theta_a = float(preparation.params["theta_a"])
        phi_a = float(preparation.params["phi_a"])
        theta_b = float(preparation.params["theta_b"])
        phi_b = float(preparation.params["phi_b"])
        wa = _dashifine_ternary_hilbert.embed_qubit_plane(theta=theta_a, phi=phi_a)
        wb = _dashifine_ternary_hilbert.embed_qubit_plane(theta=theta_b, phi=phi_b)
        a, ap, b, bp = _dashifine_embed_chsh_ternary.default_tsig_angles()
        s_op = _dashifine_embed_chsh_ternary.chsh_operators_qubit(a, ap, b, bp)
        embedded_expectation = _dashifine_embed_chsh_ternary.expectation_in_embedded_CHSH(
            _dashifine_embed_chsh_ternary.bell_phi_plus(), s_op, wa, wb
        )
        witness["embedded_reference"] = {
            "name": "embedded_CHSH_S",
            "value": embedded_expectation,
            "source": "dashifine.newtest.embed_chsh_ternary.expectation_in_embedded_CHSH",
        }
    witness["state_preparation"] = witness["prep_metadata"]
    return witness


def promotability_gap(record: MeasurementRecord) -> float:
    """Simple v1 gap: high variance is bad, CHSH violation is good."""

    deviation = max(0.0, abs(record.observable) - 2.0)
    return float(record.variance - deviation)


def qutrit_promotability_gap(record: MeasurementRecord) -> float:
    return float(record.variance - record.observable)


def triality_promotability_gap(record: MeasurementRecord) -> float:
    return float(record.variance - abs(record.observable))


def _canonical_local_plane() -> np.ndarray:
    return np.array([1.0, 0.0], dtype=complex)


def _extract_lattice_planes(
    n_a: int = 21,
    n_b: int = 21,
    t1: float = 0.7,
    t2: float = 1.3,
    wall_a: int | None = None,
    wall_b: int | None = None,
    which_block_a: str = "A",
    which_block_b: str = "A",
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if _dashifine_lattice_chsh is None:
        raise RuntimeError("lattice_chsh is unavailable")
    if wall_a is None:
        wall_a = n_a // 2
    if wall_b is None:
        wall_b = n_b // 2
    _, _, vecs_a = _dashifine_lattice_chsh.build_single_leg_open(n_a, t1, t2, wall_a)
    _, _, vecs_b = _dashifine_lattice_chsh.build_single_leg_open(n_b, t1, t2, wall_b)
    u_a, _ = _dashifine_lattice_chsh.extract_wall_qubit_frame(
        vecs_a, n_a, wall_a, which_block=which_block_a
    )
    u_b, _ = _dashifine_lattice_chsh.extract_wall_qubit_frame(
        vecs_b, n_b, wall_b, which_block=which_block_b
    )
    params = {
        "n_a": n_a,
        "n_b": n_b,
        "t1": t1,
        "t2": t2,
        "wall_a": wall_a,
        "wall_b": wall_b,
        "which_block_a": which_block_a,
        "which_block_b": which_block_b,
    }
    return u_a, u_b, params


def _extract_triality_planes(
    n: int = 21,
    t1: float = 0.7,
    t2: float = 1.3,
    g_perp: float = 0.2,
    wall: int | None = None,
    which_block: str = "A",
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if _dashifine_triality_stack is None or _dashifine_chsh_harness is None:
        raise RuntimeError("triality prep is unavailable")
    if wall is None:
        wall = n // 2
    phases_leg = [
        _dashifine_triality_stack.make_leg_phases_with_offset(n, wall, 0.0),
        _dashifine_triality_stack.make_leg_phases_with_offset(
            n, wall, 2.0 * np.pi / 3.0
        ),
        _dashifine_triality_stack.make_leg_phases_with_offset(
            n, wall, 4.0 * np.pi / 3.0
        ),
    ]
    h = _dashifine_triality_stack.build_triality_stack_H(
        N=n,
        t1=t1,
        t2=t2,
        phases_leg=phases_leg,
        domain_wall_at=wall,
        g_perp=g_perp,
    )
    _, vecs = _dashifine_triality_stack.eigh_sorted_by_abs(h)
    v0 = vecs[:, 0]
    leg_dim = 4 * n
    leg0 = v0[0:leg_dim]
    leg1 = v0[leg_dim : 2 * leg_dim]
    u_a = _dashifine_chsh_harness.extract_local_plane_basis_at_wall(
        leg0, n, wall, which_block=which_block
    )
    u_b = _dashifine_chsh_harness.extract_local_plane_basis_at_wall(
        leg1, n, wall, which_block=which_block
    )
    params = {
        "n": n,
        "t1": t1,
        "t2": t2,
        "g_perp": g_perp,
        "wall": wall,
        "which_block": which_block,
        "eigenmode_rank": 0,
        "leg_plane_vectors": {
            0: [float(np.real(u_a[0])), float(np.real(u_a[1]))],
            1: [float(np.real(u_b[0])), float(np.real(u_b[1]))],
            2: [
                float(np.real(_dashifine_chsh_harness.extract_local_plane_basis_at_wall(
                    v0[2 * leg_dim : 3 * leg_dim], n, wall, which_block=which_block
                )[0])),
                float(np.real(_dashifine_chsh_harness.extract_local_plane_basis_at_wall(
                    v0[2 * leg_dim : 3 * leg_dim], n, wall, which_block=which_block
                )[1])),
            ],
        },
    }
    return u_a, u_b, params


def prepare_state(prep_mode: str = "lattice_frames") -> tuple[QState, PreparationSpec]:
    if (
        prep_mode == "triality_frames"
        and _dashifine_triality_stack is not None
        and _dashifine_chsh_harness is not None
    ):
        u_a, u_b, params = _extract_triality_planes()
        psi = _dashifine_chsh_harness.two_qubit_from_two_local_planes(u_a, u_b)
        return (
            QState(psi, provenance={"prepared_by": "triality_frames"}),
            PreparationSpec(
                mode="triality_frames",
                source=(
                    "dashifine.newtest.triality_stack.build_triality_stack_H + "
                    "dashifine.newtest.chsh_harness.extract_local_plane_basis_at_wall + "
                    "dashifine.newtest.chsh_harness.two_qubit_from_two_local_planes"
                ),
                params=params,
                carrier="triality",
            ),
        )

    if (
        prep_mode == "lattice_frames"
        and _dashifine_lattice_chsh is not None
        and _dashifine_chsh_harness is not None
    ):
        u_a, u_b, params = _extract_lattice_planes()
        psi = _dashifine_chsh_harness.two_qubit_from_two_local_planes(u_a, u_b)
        return (
            QState(psi, provenance={"prepared_by": "lattice_frames"}),
            PreparationSpec(
                mode="lattice_frames",
                source=(
                    "dashifine.newtest.lattice_chsh.extract_wall_qubit_frame + "
                    "dashifine.newtest.chsh_harness.two_qubit_from_two_local_planes"
                ),
                params=params,
                carrier="qubit",
            ),
        )

    if (
        prep_mode == "qutrit_planes"
        and _dashifine_ternary_hilbert is not None
        and _dashifine_embed_chsh_ternary is not None
    ):
        w_a = _dashifine_ternary_hilbert.embed_qubit_plane(theta=0.0, phi=0.0)
        w_b = _dashifine_ternary_hilbert.embed_qubit_plane(theta=0.0, phi=0.0)
        psi2 = _dashifine_embed_chsh_ternary.bell_phi_plus()
        psi = _dashifine_embed_chsh_ternary.embed_two_qubits_in_two_qutrits(w_a, w_b) @ psi2
        return (
            QState(psi, basis="qutrit_computational", provenance={"prepared_by": "qutrit_planes"}),
            PreparationSpec(
                mode="qutrit_planes",
                source=(
                    "dashifine.newtest.ternary_hilbert.embed_qubit_plane + "
                    "dashifine.newtest.embed_chsh_ternary.embed_two_qubits_in_two_qutrits + "
                    "dashifine.newtest.embed_chsh_ternary.bell_phi_plus"
                ),
                params={
                    "theta_a": 0.0,
                    "phi_a": 0.0,
                    "theta_b": 0.0,
                    "phi_b": 0.0,
                    "embedded_dimensions": [int(w_a.shape[0]), int(w_b.shape[0])],
                    "embedded_observable": "embedded_CHSH_S",
                },
                carrier="qutrit",
            ),
        )

    if prep_mode == "local_planes" and _dashifine_chsh_harness is not None:
        u_a = _canonical_local_plane()
        u_b = _canonical_local_plane()
        psi = _dashifine_chsh_harness.two_qubit_from_two_local_planes(u_a, u_b)
        return (
            QState(psi, provenance={"prepared_by": "local_planes"}),
            PreparationSpec(
                mode="local_planes",
                source="dashifine.newtest.chsh_harness.two_qubit_from_two_local_planes",
                params={"u_a": [1.0, 0.0], "u_b": [1.0, 0.0]},
                carrier="qubit",
            ),
        )

    if prep_mode == "ideal_bell" and _dashifine_lattice_chsh is not None:
        psi = _dashifine_lattice_chsh.prepare_two_qubit_state("ideal_bell")
        return (
            QState(psi, provenance={"prepared_by": "ideal_bell"}),
            PreparationSpec(
                mode="ideal_bell",
                source="dashifine.newtest.lattice_chsh.prepare_two_qubit_state[ideal_bell]",
                params={"mode": "ideal_bell"},
                carrier="qubit",
            ),
        )

    if _dashifine_chsh_harness is not None:
        psi = _dashifine_chsh_harness.bell_state_phi_plus()
        return (
            QState(psi, provenance={"prepared_by": "bell_state_phi_plus"}),
            PreparationSpec(
                mode="ideal_bell",
                source="dashifine.newtest.chsh_harness.bell_state_phi_plus",
                params={"mode": "ideal_bell"},
                carrier="qubit",
            ),
        )

    psi = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2.0)
    return (
        QState(psi, provenance={"prepared_by": "local_fallback"}),
        PreparationSpec(mode="ideal_bell", source="local_fallback", params=None, carrier="qubit"),
    )


def j_rotation(theta: float = 0.3) -> UnitaryOp:
    if _dashifine_triality_stack is not None:
        u_single = _dashifine_triality_stack.R(theta).astype(complex)
    else:
        j = np.array([[0, -1], [1, 0]], dtype=complex)
        u_single = np.cos(theta) * np.eye(2, dtype=complex) + np.sin(theta) * j
    unitary = kron(u_single, u_single)
    return UnitaryOp(unitary, name="J_rotation")


def run_computer_v1(
    shots: int = 200,
    noise_scale: float = 0.0,
    theta: float = 0.3,
    prep_mode: str = "lattice_frames",
    rng: np.random.Generator | None = None,
) -> dict[str, Any]:
    state, preparation = prepare_state(prep_mode=prep_mode)
    if preparation.carrier == "qutrit":
        evolution = UnitaryOp(
            kron(_dashifine_ternary_hilbert.Z_qutrit(), _dashifine_ternary_hilbert.Z_qutrit()),
            name="qutrit_phase_rotation",
        )
        measurement = MeasurementOp({}, name="qutrit_basis_measurement")
        system = QuantumSys(state, evolution, measurement)
        system.evolve(steps=1)
        record = qutrit_native_measurement(system.state, shots=shots, rng=rng)
        policy = QutritPromotionPolicy()
        promotion = policy.decide(record)
        gap = qutrit_promotability_gap(record)
    elif preparation.carrier == "triality":
        evolution = j_rotation(theta=theta)
        measurement = MeasurementOp({}, name="triality_pair_measurement")
        system = QuantumSys(state, evolution, measurement)
        system.evolve(steps=1)
        record = triality_native_measurement(
            system.state,
            preparation=preparation,
            shots=shots,
            rng=rng,
            noise_scale=noise_scale,
        )
        policy = TrialityPromotionPolicy()
        promotion = policy.decide(record)
        gap = triality_promotability_gap(record)
    else:
        evolution = j_rotation(theta=theta)
        measurement = MeasurementOp(chsh_operators(), name="CHSH")
        system = QuantumSys(state, evolution, measurement)
        system.evolve(steps=1)
        record = system.run_measurement(shots=shots, rng=rng, noise_scale=noise_scale)
        policy = PromotionPolicy()
        promotion = policy.decide(record)
        gap = promotability_gap(record)
    witness = build_witness(system, record, preparation)
    witness["promotion"] = {
        "accepted": promotion.accepted,
        "reason": promotion.reason,
    }
    return {
        "record": record,
        "promotion": promotion,
        "witness": witness,
        "gap": gap,
    }


if __name__ == "__main__":
    output = run_computer_v1()
    print("\n=== Measurement Record ===")
    print(output["record"])
    print("\n=== Promotion ===")
    print(output["promotion"])
    print("\n=== Witness ===")
    for key, value in output["witness"].items():
        print(f"{key}: {value}")
    print("\n=== Gap ===")
    print(output["gap"])
