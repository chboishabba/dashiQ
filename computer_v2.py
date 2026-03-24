"""Typed multi-carrier quantum bridge for dashiQ.

This module keeps carrier semantics explicit:

- `QUBIT` uses CHSH-style two-qubit observables.
- `QUTRIT` uses qutrit-native observables, including a richer 27->9 motif path.
- `TRIALITY` uses pair-selection and pair-correlation on wall-mode planes.

It reuses the proven `dashifine/newtest` seams through `computer_v1` where
possible, but stops the bridge from collapsing back into ad hoc branching.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

import numpy as np

import computer_v1 as _v1


@dataclass(frozen=True)
class QState:
    vector: np.ndarray
    basis: str = "computational"
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "vector", _normalize(self.vector))
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@dataclass(frozen=True)
class PromotionResult:
    accepted: bool
    reason: str
    datum: dict[str, Any]


class UnitaryOp:
    def __init__(self, unitary: np.ndarray, name: str = "U", exact: bool = True):
        matrix = np.asarray(unitary, dtype=complex)
        if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
            raise ValueError("unitary must be square")
        self.U = matrix
        self.U_inv = matrix.conj().T
        self.name = name
        self.exact = exact

    def step(self, state: QState) -> QState:
        metadata = dict(state.metadata)
        metadata["last_unitary"] = self.name
        return QState(self.U @ state.vector, basis=state.basis, metadata=metadata)

    def inv(self, state: QState) -> QState:
        metadata = dict(state.metadata)
        metadata["last_unitary_inv"] = self.name
        return QState(self.U_inv @ state.vector, basis=state.basis, metadata=metadata)


class CarrierType(str, Enum):
    QUBIT = "qubit"
    QUTRIT = "qutrit"
    TRIALITY = "triality"


@dataclass(frozen=True)
class CarrierSpec:
    carrier_type: CarrierType
    name: str
    dimension: int
    prep_metadata: dict[str, Any]


@dataclass(frozen=True)
class QubitMeasurementRecord:
    datum: dict[str, float]
    projected_state: QState
    observable: float
    shots: int
    variance: float
    measurement_kind: str = "chsh_expectation"


@dataclass(frozen=True)
class QutritMeasurementRecord:
    datum: dict[str, Any]
    projected_state: QState
    probs: np.ndarray
    entropy: float
    entropy_gap: float
    shots: int
    variance: float
    observable_family: str
    measurement_kind: str


@dataclass(frozen=True)
class TrialityMeasurementRecord:
    datum: dict[str, Any]
    projected_state: QState
    selected_pair: tuple[int, int]
    correlation: float
    shots: int
    variance: float
    measurement_kind: str = "triality_pair_correlation"


class MeasurementStrategy(Protocol):
    def run(self, state: QState, shots: int) -> Any: ...


class PromotionStrategy(Protocol):
    def decide(self, record: Any) -> PromotionResult: ...


class WitnessStrategy(Protocol):
    def build(
        self,
        carrier: CarrierSpec,
        evolution: UnitaryOp,
        record: Any,
        promotion: PromotionResult,
    ) -> dict[str, Any]: ...


def _normalize(vector: np.ndarray) -> np.ndarray:
    array = np.asarray(vector, dtype=complex)
    norm = np.linalg.norm(array)
    if norm <= 0.0:
        raise ValueError("state must have nonzero norm")
    return array / norm


def _project(state: QState, projected_by: str) -> QState:
    metadata = dict(state.metadata)
    metadata["projected_by"] = projected_by
    return QState(state.vector, basis=state.basis, metadata=metadata)


def _shannon_entropy(probabilities: np.ndarray) -> float:
    probs = np.asarray(probabilities, dtype=float)
    probs = probs[probs > 0.0]
    if probs.size == 0:
        return 0.0
    return float(-np.sum(probs * np.log(probs)))


class QubitMeasurement:
    def __init__(self) -> None:
        self._measurement = _v1.MeasurementOp(_v1.chsh_operators(), name="CHSH")

    def run(self, state: QState, shots: int) -> QubitMeasurementRecord:
        system = _v1.QuantumSys(
            _v1.QState(state.vector, basis=state.basis, provenance=dict(state.metadata)),
            _v1.UnitaryOp(np.eye(state.vector.shape[0], dtype=complex), name="identity"),
            self._measurement,
        )
        record = system.run_measurement(shots=shots)
        return QubitMeasurementRecord(
            datum=record.datum,
            projected_state=QState(
                record.projected_state.vector,
                basis=record.projected_state.basis,
                metadata=record.projected_state.provenance,
            ),
            observable=record.observable,
            shots=record.shots,
            variance=record.variance,
            measurement_kind=record.measurement_kind,
        )


class QutritMeasurement:
    def __init__(self, carrier: CarrierSpec, rng: np.random.Generator | None = None):
        self.carrier = carrier
        self.rng = rng or np.random.default_rng()
        self.observable_family = str(
            carrier.prep_metadata.get("observable_family", "basis9_entropy")
        )

    def _measure_basis9(self, state: QState, shots: int) -> QutritMeasurementRecord:
        probabilities = np.abs(state.vector) ** 2
        probabilities = probabilities / probabilities.sum()
        sample_indices = self.rng.choice(9, size=shots, p=probabilities)
        counts = np.bincount(sample_indices, minlength=9)
        frequencies = counts / float(shots)
        max_entropy = float(np.log(9.0))
        entropy = _shannon_entropy(frequencies)
        entropy_gap = max_entropy - entropy
        one_shot_entropies = []
        for index in sample_indices:
            one_hot = np.zeros(9, dtype=float)
            one_hot[index] = 1.0
            one_shot_entropies.append(_shannon_entropy(one_hot))
        variance = float(np.var(one_shot_entropies + [entropy]))
        labels = [f"{i}{j}" for i in range(3) for j in range(3)]
        datum = {label: float(value) for label, value in zip(labels, frequencies)}
        collapsed = np.zeros(9, dtype=complex)
        collapsed[int(np.argmax(frequencies))] = 1.0
        return QutritMeasurementRecord(
            datum=datum,
            projected_state=QState(
                collapsed,
                basis="qutrit_computational",
                metadata={**state.metadata, "projected_by": "qutrit_basis_measurement"},
            ),
            probs=frequencies,
            entropy=entropy,
            entropy_gap=entropy_gap,
            shots=shots,
            variance=variance,
            observable_family="basis9_entropy",
            measurement_kind="qutrit_distribution_entropy_gap",
        )

    def _measure_motif27(self, state: QState, shots: int) -> QutritMeasurementRecord:
        if _v1._dashifine_map_27_to_H3x3 is None:
            raise RuntimeError("27->9 motif path requires dashifine map_27_to_H3x3")
        probabilities_27 = np.abs(state.vector) ** 2
        probabilities_27 = probabilities_27 / probabilities_27.sum()
        motif_probs = _v1._dashifine_map_27_to_H3x3.coarse9_from_weights27(probabilities_27)
        sample_indices = self.rng.choice(9, size=shots, p=motif_probs)
        counts = np.bincount(sample_indices, minlength=9)
        frequencies = counts / float(shots)
        max_entropy = float(np.log(9.0))
        entropy = _shannon_entropy(frequencies)
        entropy_gap = max_entropy - entropy
        one_shot_entropies = []
        for index in sample_indices:
            one_hot = np.zeros(9, dtype=float)
            one_hot[index] = 1.0
            one_shot_entropies.append(_shannon_entropy(one_hot))
        variance = float(np.var(one_shot_entropies + [entropy]))
        labels = [f"motif_{index}" for index in range(9)]
        datum = {
            "motif_probs": {label: float(value) for label, value in zip(labels, frequencies)},
            "latent_support_27": int(np.count_nonzero(probabilities_27 > 1e-12)),
            "coarse_graining": "dashifine.newtest.map_27_to_H3x3.coarse9_from_weights27",
        }
        collapsed = np.zeros(9, dtype=complex)
        collapsed[int(np.argmax(frequencies))] = 1.0
        return QutritMeasurementRecord(
            datum=datum,
            projected_state=QState(
                collapsed,
                basis="motif9",
                metadata={**state.metadata, "projected_by": "qutrit_motif_measurement"},
            ),
            probs=frequencies,
            entropy=entropy,
            entropy_gap=entropy_gap,
            shots=shots,
            variance=variance,
            observable_family="motif9_entropy",
            measurement_kind="qutrit_motif27_entropy_gap",
        )

    def run(self, state: QState, shots: int) -> QutritMeasurementRecord:
        if shots <= 0:
            raise ValueError("shots must be positive")
        if state.vector.shape[0] == 27 or self.observable_family == "motif9_entropy":
            return self._measure_motif27(state, shots)
        if state.vector.shape[0] != 9:
            raise ValueError("qutrit basis measurement expects a 9D or 27D state")
        return self._measure_basis9(state, shots)


class TrialityMeasurement:
    def __init__(self, carrier: CarrierSpec):
        planes = carrier.prep_metadata.get("leg_plane_vectors")
        if planes is None:
            raise ValueError("triality carrier requires leg_plane_vectors")
        self.planes = {
            int(key): np.asarray(value, dtype=complex) for key, value in planes.items()
        }

    def run(self, state: QState, shots: int) -> TrialityMeasurementRecord:
        generator = np.random.default_rng()
        pairs = ((0, 1), (0, 2), (1, 2))
        samples: list[dict[tuple[int, int], float]] = []
        for _ in range(shots):
            sample: dict[tuple[int, int], float] = {}
            for pair in pairs:
                base = float(abs(np.vdot(self.planes[pair[0]], self.planes[pair[1]])))
                sample[pair] = float(np.clip(base + generator.normal(0.0, 0.0), 0.0, 1.0))
            samples.append(sample)
        mean_scores = {
            pair: float(np.mean([sample[pair] for sample in samples])) for pair in pairs
        }
        selected_pair = max(mean_scores, key=lambda pair: abs(mean_scores[pair]))
        correlation = mean_scores[selected_pair]
        variance = float(np.var([sample[selected_pair] for sample in samples]))
        return TrialityMeasurementRecord(
            datum={
                "selected_pair": list(selected_pair),
                "pair_scores": {f"{i}{j}": value for (i, j), value in mean_scores.items()},
            },
            projected_state=_project(state, "triality_pair_measurement"),
            selected_pair=selected_pair,
            correlation=correlation,
            shots=shots,
            variance=variance,
        )


class QubitPromotion:
    def __init__(self, s_threshold: float = 2.0, var_threshold: float = 0.05):
        self.s_threshold = s_threshold
        self.var_threshold = var_threshold

    def decide(self, record: QubitMeasurementRecord) -> PromotionResult:
        if record.variance > self.var_threshold:
            return PromotionResult(False, "high_variance", record.datum)
        if abs(record.observable) > self.s_threshold:
            return PromotionResult(True, "nonlocal_signal", record.datum)
        return PromotionResult(False, "classical_or_weak_signal", record.datum)


class QutritPromotion:
    def __init__(self, entropy_var_threshold: float = 0.02, min_entropy_gap: float = 0.10):
        self.entropy_var_threshold = entropy_var_threshold
        self.min_entropy_gap = min_entropy_gap

    def decide(self, record: QutritMeasurementRecord) -> PromotionResult:
        datum = dict(record.datum)
        datum["entropy"] = record.entropy
        datum["entropy_gap"] = record.entropy_gap
        if record.variance > self.entropy_var_threshold:
            return PromotionResult(False, "high_entropy_variance", datum)
        if record.entropy_gap > self.min_entropy_gap:
            if record.observable_family == "motif9_entropy":
                return PromotionResult(True, "structured_qutrit_motif_distribution", datum)
            return PromotionResult(True, "structured_qutrit_distribution", datum)
        if record.observable_family == "motif9_entropy":
            return PromotionResult(False, "near_uniform_qutrit_motif_distribution", datum)
        return PromotionResult(False, "near_uniform_qutrit_distribution", datum)


class TrialityPromotion:
    def __init__(self, corr_threshold: float = 0.5, var_threshold: float = 0.05):
        self.corr_threshold = corr_threshold
        self.var_threshold = var_threshold

    def decide(self, record: TrialityMeasurementRecord) -> PromotionResult:
        if record.variance > self.var_threshold:
            return PromotionResult(False, "unstable_pair", record.datum)
        if abs(record.correlation) < self.corr_threshold:
            return PromotionResult(False, "weak_signal", record.datum)
        return PromotionResult(True, f"selected_pair_{record.selected_pair}", record.datum)


class QubitWitness:
    def build(
        self,
        carrier: CarrierSpec,
        evolution: UnitaryOp,
        record: QubitMeasurementRecord,
        promotion: PromotionResult,
    ) -> dict[str, Any]:
        return {
            "witness_schema": "dashiQ.quantum_bridge.v2",
            "source_semantics": "2-qubit Hilbert state",
            "carrier": carrier.carrier_type.value,
            "carrier_name": carrier.name,
            "prep_metadata": carrier.prep_metadata,
            "evolution": {
                "type": evolution.name,
                "exact": evolution.exact,
                "invertible": True,
            },
            "measurement": {
                "type": "chsh",
                "projection": "idempotent_normalization",
                "quotient": True,
                "source": (
                    "dashifine.newtest.chsh_harness.chsh_S"
                    if _v1._dashifine_chsh_harness is not None
                    else "local_fallback"
                ),
            },
            "observable": {
                "name": "CHSH_S",
                "value": record.observable,
                "variance": record.variance,
                "shots": record.shots,
                "bounds": {"classical": 2.0, "quantum": float(2.0 * np.sqrt(2.0))},
            },
            "measurement_kind": record.measurement_kind,
            "promotion": {
                "accepted": promotion.accepted,
                "reason": promotion.reason,
            },
            "claim_status": (
                "exact_evolution_statistical_observable"
                if record.variance > 0.0
                else "exact_evolution_observable"
            ),
        }


class QutritWitness:
    def build(
        self,
        carrier: CarrierSpec,
        evolution: UnitaryOp,
        record: QutritMeasurementRecord,
        promotion: PromotionResult,
    ) -> dict[str, Any]:
        witness = {
            "witness_schema": "dashiQ.quantum_bridge.v2",
            "source_semantics": (
                "motif-coarse-grained triplet state"
                if record.observable_family == "motif9_entropy"
                else "two-qutrit embedded state"
            ),
            "carrier": carrier.carrier_type.value,
            "carrier_name": carrier.name,
            "prep_metadata": carrier.prep_metadata,
            "evolution": {
                "type": evolution.name,
                "exact": evolution.exact,
                "invertible": True,
            },
            "measurement": {
                "type": (
                    "motif_probability_simplex"
                    if record.observable_family == "motif9_entropy"
                    else "probability_simplex"
                ),
                "projection": "idempotent_normalization",
                "quotient": True,
            },
            "observable": {
                "name": (
                    "motif_entropy_gap_over_27_to_9"
                    if record.observable_family == "motif9_entropy"
                    else "entropy_gap_over_qutrit_basis"
                ),
                "value": record.entropy_gap,
                "entropy": record.entropy,
                "variance": record.variance,
                "shots": record.shots,
                "bounds": {"min": 0.0, "max": float(np.log(9.0))},
            },
            "distribution": record.datum,
            "measurement_kind": record.measurement_kind,
            "promotion": {
                "accepted": promotion.accepted,
                "reason": promotion.reason,
            },
            "claim_status": "statistical_entropy_observable",
        }
        if record.observable_family == "basis9_entropy":
            theta_a = float(carrier.prep_metadata.get("theta_a", 0.0))
            phi_a = float(carrier.prep_metadata.get("phi_a", 0.0))
            theta_b = float(carrier.prep_metadata.get("theta_b", 0.0))
            phi_b = float(carrier.prep_metadata.get("phi_b", 0.0))
            wa = _v1._dashifine_ternary_hilbert.embed_qubit_plane(theta=theta_a, phi=phi_a)
            wb = _v1._dashifine_ternary_hilbert.embed_qubit_plane(theta=theta_b, phi=phi_b)
            a, ap, b, bp = _v1._dashifine_embed_chsh_ternary.default_tsig_angles()
            s_op = _v1._dashifine_embed_chsh_ternary.chsh_operators_qubit(a, ap, b, bp)
            embedded_expectation = _v1._dashifine_embed_chsh_ternary.expectation_in_embedded_CHSH(
                _v1._dashifine_embed_chsh_ternary.bell_phi_plus(), s_op, wa, wb
            )
            witness["embedded_reference"] = {
                "name": "embedded_CHSH_S",
                "value": embedded_expectation,
            }
        return witness


class TrialityWitness:
    def build(
        self,
        carrier: CarrierSpec,
        evolution: UnitaryOp,
        record: TrialityMeasurementRecord,
        promotion: PromotionResult,
    ) -> dict[str, Any]:
        return {
            "witness_schema": "dashiQ.quantum_bridge.v2",
            "source_semantics": "triality wall-mode pair",
            "carrier": carrier.carrier_type.value,
            "carrier_name": carrier.name,
            "prep_metadata": carrier.prep_metadata,
            "evolution": {
                "type": evolution.name,
                "exact": evolution.exact,
                "invertible": True,
            },
            "measurement": {
                "type": "pair_correlation",
                "projection": "idempotent_normalization",
                "quotient": True,
            },
            "selection": {
                "pair": list(record.selected_pair),
                "rule": "max_abs_correlation",
                "pair_scores": record.datum.get("pair_scores"),
            },
            "observable": {
                "name": "pair_correlation",
                "value": record.correlation,
                "variance": record.variance,
                "shots": record.shots,
                "bounds": {"min": 0.0, "max": 1.0},
            },
            "measurement_kind": record.measurement_kind,
            "promotion": {
                "accepted": promotion.accepted,
                "reason": promotion.reason,
            },
            "claim_status": "statistical_pair_observable",
        }


@dataclass(frozen=True)
class CarrierRuntime:
    measurement: MeasurementStrategy
    promotion: PromotionStrategy
    witness: WitnessStrategy


@dataclass(frozen=True)
class PipelineJob:
    carrier: CarrierSpec
    initial_state: QState
    evolution: UnitaryOp


def build_runtime(carrier: CarrierSpec) -> CarrierRuntime:
    if carrier.carrier_type == CarrierType.QUBIT:
        return CarrierRuntime(
            measurement=QubitMeasurement(),
            promotion=QubitPromotion(),
            witness=QubitWitness(),
        )
    if carrier.carrier_type == CarrierType.QUTRIT:
        return CarrierRuntime(
            measurement=QutritMeasurement(carrier),
            promotion=QutritPromotion(),
            witness=QutritWitness(),
        )
    if carrier.carrier_type == CarrierType.TRIALITY:
        return CarrierRuntime(
            measurement=TrialityMeasurement(carrier),
            promotion=TrialityPromotion(),
            witness=TrialityWitness(),
        )
    raise ValueError(f"unsupported carrier type: {carrier.carrier_type}")


def promotability_gap(record: Any, carrier_type: CarrierType) -> float:
    if carrier_type == CarrierType.QUBIT:
        deviation = max(0.0, abs(record.observable) - 2.0)
        return float(record.variance - deviation)
    if carrier_type == CarrierType.QUTRIT:
        return float(record.variance - record.entropy_gap)
    if carrier_type == CarrierType.TRIALITY:
        return float(record.variance - abs(record.correlation))
    raise ValueError(f"unsupported carrier type: {carrier_type}")


def run_typed_pipeline(job: PipelineJob, shots: int = 200) -> dict[str, Any]:
    runtime = build_runtime(job.carrier)
    evolved_state = job.evolution.step(job.initial_state)
    record = runtime.measurement.run(evolved_state, shots=shots)
    promotion = runtime.promotion.decide(record)
    witness = runtime.witness.build(job.carrier, job.evolution, record, promotion)
    gap = promotability_gap(record, job.carrier.carrier_type)
    return {
        "carrier": job.carrier,
        "state_in": job.initial_state,
        "state_out": evolved_state,
        "record": record,
        "promotion": promotion,
        "witness": witness,
        "gap": gap,
    }


def _kron(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.kron(a, b)


def _qutrit_phase_rotation() -> UnitaryOp:
    z = _v1._dashifine_ternary_hilbert.Z_qutrit()
    return UnitaryOp(_kron(z, z), name="qutrit_phase_rotation")


def prepare_qubit_lattice_job(theta: float = 0.3) -> PipelineJob:
    u_a, u_b, params = _v1._extract_lattice_planes()
    psi = _v1._dashifine_chsh_harness.two_qubit_from_two_local_planes(u_a, u_b)
    return PipelineJob(
        carrier=CarrierSpec(
            carrier_type=CarrierType.QUBIT,
            name="lattice_frames",
            dimension=4,
            prep_metadata={
                "source": (
                    "dashifine.newtest.lattice_chsh.extract_wall_qubit_frame + "
                    "dashifine.newtest.chsh_harness.two_qubit_from_two_local_planes"
                ),
                **params,
            },
        ),
        initial_state=QState(psi, metadata={"prepared_by": "lattice_frames"}),
        evolution=UnitaryOp(_v1.j_rotation(theta).U, name="J_rotation"),
    )


def prepare_triality_job(theta: float = 0.3) -> PipelineJob:
    u_a, u_b, params = _v1._extract_triality_planes()
    psi = _v1._dashifine_chsh_harness.two_qubit_from_two_local_planes(u_a, u_b)
    return PipelineJob(
        carrier=CarrierSpec(
            carrier_type=CarrierType.TRIALITY,
            name="triality_frames",
            dimension=4,
            prep_metadata={
                "source": (
                    "dashifine.newtest.triality_stack.build_triality_stack_H + "
                    "dashifine.newtest.chsh_harness.extract_local_plane_basis_at_wall + "
                    "dashifine.newtest.chsh_harness.two_qubit_from_two_local_planes"
                ),
                **params,
            },
        ),
        initial_state=QState(psi, metadata={"prepared_by": "triality_frames"}),
        evolution=UnitaryOp(_v1.j_rotation(theta).U, name="J_rotation"),
    )


def prepare_qutrit_planes_job() -> PipelineJob:
    w_a = _v1._dashifine_ternary_hilbert.embed_qubit_plane(theta=0.0, phi=0.0)
    w_b = _v1._dashifine_ternary_hilbert.embed_qubit_plane(theta=0.0, phi=0.0)
    psi2 = _v1._dashifine_embed_chsh_ternary.bell_phi_plus()
    lift = _v1._dashifine_embed_chsh_ternary.embed_two_qubits_in_two_qutrits(w_a, w_b)
    psi = lift @ psi2
    return PipelineJob(
        carrier=CarrierSpec(
            carrier_type=CarrierType.QUTRIT,
            name="qutrit_planes",
            dimension=9,
            prep_metadata={
                "source": (
                    "dashifine.newtest.ternary_hilbert.embed_qubit_plane + "
                    "dashifine.newtest.embed_chsh_ternary.embed_two_qubits_in_two_qutrits + "
                    "dashifine.newtest.embed_chsh_ternary.bell_phi_plus"
                ),
                "observable_family": "basis9_entropy",
                "theta_a": 0.0,
                "phi_a": 0.0,
                "theta_b": 0.0,
                "phi_b": 0.0,
            },
        ),
        initial_state=QState(
            psi, basis="qutrit_computational", metadata={"prepared_by": "qutrit_planes"}
        ),
        evolution=_qutrit_phase_rotation(),
    )


def prepare_qutrit_motif27_job() -> PipelineJob:
    if _v1._dashifine_map_27_to_H3x3 is None:
        raise RuntimeError("qutrit motif path requires dashifine map_27_to_H3x3")
    triplets = ((0, 1, 2), (1, 1, 1), (0, 0, 1))
    amplitudes = np.array([0.62, 0.56, 0.55], dtype=complex)
    psi = sum(
        amp * _v1._dashifine_map_27_to_H3x3.triplet_ket(i, j, k)
        for amp, (i, j, k) in zip(amplitudes, triplets)
    )
    probabilities_27 = _v1._dashifine_map_27_to_H3x3.mix_over_27(np.abs(psi) ** 2)
    psi = np.sqrt(probabilities_27).astype(complex)
    motif_seed = _v1._dashifine_map_27_to_H3x3.coarse9_from_weights27(probabilities_27)
    return PipelineJob(
        carrier=CarrierSpec(
            carrier_type=CarrierType.QUTRIT,
            name="qutrit_motif27",
            dimension=27,
            prep_metadata={
                "source": (
                    "dashifine.newtest.map_27_to_H3x3.triplet_ket + "
                    "dashifine.newtest.map_27_to_H3x3.mix_over_27 + "
                    "dashifine.newtest.map_27_to_H3x3.coarse9_from_weights27"
                ),
                "observable_family": "motif9_entropy",
                "motif_seed": motif_seed.tolist(),
                "latent_support_27": int(np.count_nonzero(probabilities_27)),
                "triplet_basis_components": [list(triplet) for triplet in triplets],
            },
        ),
        initial_state=QState(psi, basis="triplet27", metadata={"prepared_by": "qutrit_motif27"}),
        evolution=UnitaryOp(np.eye(27, dtype=complex), name="motif_identity"),
    )


def demo() -> None:
    jobs = [
        prepare_qubit_lattice_job(),
        prepare_qutrit_planes_job(),
        prepare_qutrit_motif27_job(),
        prepare_triality_job(),
    ]
    for job in jobs:
        output = run_typed_pipeline(job, shots=128)
        print(f"\n=== {job.carrier.name} ({job.carrier.carrier_type.value}) ===")
        print("promotion:", output["promotion"])
        print("gap:", output["gap"])
        print("observable:", output["witness"]["observable"])


if __name__ == "__main__":
    demo()
