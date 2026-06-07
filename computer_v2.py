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
import datetime as _dt
import json
from pathlib import Path
from enum import Enum
from typing import Any, Protocol

import numpy as np

import computer_v1 as _v1
import qg_motif_models as _qg_models


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
    projection_scores: dict[str, dict[str, float]]
    selected_projection: str
    selected_projection_score: float
    observable_family: str
    measurement_kind: str
    selection_rule: str = "entropy_gap_projection_selection"


@dataclass(frozen=True)
class TrialityMeasurementRecord:
    datum: dict[str, Any]
    projected_state: QState
    selected_pair: tuple[int, int]
    correlation: float
    selected_pair_score: float
    shots: int
    variance: float
    pair_scores: dict[str, dict[str, float]]
    selection_rule: str = "multi_criterion_pair_selection"
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


def _trit_nz(value: int) -> int:
    return 0 if int(value) == 0 else 1


def _coarse_pattern_penalty(i: int, j: int) -> float:
    if i == j:
        return 0.0
    if i == 0 or j == 0:
        return 0.35
    return 0.75


def motif_weights27_qg(
    beta_model: float = 2.5,
    beta_resid: float = 1.15,
    beta_pattern: float = 0.60,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Agda-inspired 27-state motif weights from ternary coarse/tail MDL.

    This mirrors the `m = 2, k = 1` reading of the Agda shift instance:

    - coarse/model part: first two trits
    - residual/tail part: final trit
    - MDL cost: countNZ(coarse) + countNZ(tail)

    We turn that count-based cost into a Boltzmann-style weight so lower-MDL
    triplets dominate while still leaving full latent support over `Trit^3`.
    """

    weights = np.zeros(27, dtype=float)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                model_len = _trit_nz(i) + _trit_nz(j)
                resid_len = _trit_nz(k)
                pattern_len = _coarse_pattern_penalty(i, j)
                mdl_cost = (
                    beta_model * model_len
                    + beta_resid * resid_len
                    + beta_pattern * pattern_len
                )
                idx = 9 * i + 3 * j + k
                weights[idx] = float(np.exp(-mdl_cost))

    weights /= float(np.sum(weights))
    coarse9 = weights.reshape(3, 3, 3).sum(axis=2).reshape(9)
    return weights, {
        "agda_source": (
            "DASHI.Physics.LiftToFullState.coarseProj + "
            "DASHI.Physics.Closure.MDLTradeoffShiftInstance.MDLPartsShift"
        ),
        "coarse_tail_split": {"m": 2, "k": 1},
        "beta_model": beta_model,
        "beta_resid": beta_resid,
        "beta_pattern": beta_pattern,
        "model_len": "countNZ(coarse)",
        "resid_len": "countNZ(tail)",
        "pattern_len": "coarse disagreement / code penalty",
        "coarse_observable_eliminates_tail_scale": True,
        "latent_support_27": int(np.count_nonzero(weights)),
        "coarse_support_9": int(np.count_nonzero(coarse9)),
        "coarse_entropy": _shannon_entropy(coarse9),
    }


def _cyclic_triplet_views(i: int, j: int, k: int) -> tuple[tuple[int, int, int], ...]:
    return ((i, j, k), (j, k, i), (k, i, j))


def motif_weights27_qg_dynamics(
    beta_model: float = 2.5,
    beta_resid: float = 1.15,
    beta_pattern: float = 0.60,
    beta_cycle: float = 0.85,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Agda-inspired ensemble over cyclic coarse/tail views.

    For `Vec Trit 3` with `m=2, k=1`, a single fixed split leaves the coarse
    observable invariant under `Tᵣ`. To get a dynamics-sensitive motif source,
    we treat the latent triplet as an ensemble over the three cyclic choices of
    coarse-pair + tail coordinate and average their code costs.
    """

    static_weights, static_meta = motif_weights27_qg(
        beta_model=beta_model,
        beta_resid=beta_resid,
        beta_pattern=beta_pattern,
    )
    weights = np.zeros(27, dtype=float)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                idx = 9 * i + 3 * j + k
                view_costs = []
                for a, b, tail in _cyclic_triplet_views(i, j, k):
                    model_len = _trit_nz(a) + _trit_nz(b)
                    resid_len = _trit_nz(tail)
                    pattern_len = _coarse_pattern_penalty(a, b)
                    view_costs.append(
                        beta_model * model_len
                        + beta_resid * resid_len
                        + beta_pattern * pattern_len
                    )
                dynamic_cost = float(np.mean(view_costs))
                cycle_score = float(np.exp(-beta_cycle * dynamic_cost))
                weights[idx] = static_weights[idx] * cycle_score

    weights /= float(np.sum(weights))
    coarse9 = weights.reshape(3, 3, 3).sum(axis=2).reshape(9)
    return weights, {
        "agda_source": (
            "DASHI.Physics.TailCollapseProof.Tᵣ/iterate + "
            "DASHI.Physics.LiftToFullState.coarseProj + "
            "DASHI.Physics.Closure.MDLTradeoffShiftInstance.MDLPartsShift"
        ),
        "dynamics_model": "cyclic_coarse_tail_ensemble",
        "coarse_tail_split": {"m": 2, "k": 1},
        "beta_model": beta_model,
        "beta_resid": beta_resid,
        "beta_pattern": beta_pattern,
        "beta_cycle": beta_cycle,
        "cyclic_views": ["(i,j)|k", "(j,k)|i", "(k,i)|j"],
        "reference_prior": static_meta,
        "latent_support_27": int(np.count_nonzero(weights)),
        "coarse_support_9": int(np.count_nonzero(coarse9)),
        "coarse_entropy": _shannon_entropy(coarse9),
    }


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

    def _basis9_index(self, a: int, b: int) -> int:
        return (a % 3) * 3 + (b % 3)

    def _permute_basis9(self, shift_a: int = 0, shift_b: int = 0, swap: bool = False) -> list[int]:
        mapping: list[int] = []
        for a in range(3):
            for b in range(3):
                aa, bb = (b, a) if swap else (a, b)
                aa = (aa + shift_a) % 3
                bb = (bb + shift_b) % 3
                mapping.append(self._basis9_index(aa, bb))
        return mapping

    def _projection_candidates_basis9(self, probabilities: np.ndarray) -> dict[str, np.ndarray]:
        base = np.asarray(probabilities, dtype=float)
        return {
            "basis9_identity": base,
            "basis9_swapped": base[self._permute_basis9(swap=True)],
            "basis9_shift_a": base[self._permute_basis9(shift_a=1)],
            "basis9_shift_b": base[self._permute_basis9(shift_b=1)],
        }

    def _projection_candidates_motif9(self, probabilities: np.ndarray) -> dict[str, np.ndarray]:
        base = np.asarray(probabilities, dtype=float)
        return {
            "motif_identity": base,
            "motif_roll_1": np.roll(base, 1),
            "motif_roll_2": np.roll(base, 2),
            "motif_roll_3": np.roll(base, 3),
        }

    def _score_projection(self, probabilities: np.ndarray) -> tuple[float, dict[str, float]]:
        dim = float(probabilities.shape[0])
        max_entropy = float(np.log(dim))
        entropy = _shannon_entropy(probabilities)
        entropy_gap = max_entropy - entropy
        coherence = float(np.sum(probabilities ** 2))
        entropy_gap_norm = entropy_gap / max_entropy if max_entropy > 0 else 0.0
        coherence_term = (coherence - 1.0 / dim) / (1.0 - 1.0 / dim) if dim > 1 else 0.0
        score = float(0.80 * entropy_gap_norm + 0.20 * coherence_term)
        return score, {
            "entropy": entropy,
            "entropy_gap": entropy_gap,
            "coherence": coherence,
            "score": score,
            "max_entropy": max_entropy,
        }

    def _select_projection(
        self,
        candidates: dict[str, np.ndarray],
    ) -> tuple[str, np.ndarray, float, dict[str, dict[str, float]], dict[str, float]]:
        projection_scores: dict[str, dict[str, float]] = {}
        values: dict[str, float] = {}
        for name, probs in candidates.items():
            score, metrics = self._score_projection(probs)
            projection_scores[name] = metrics
            values[name] = score

        selected_projection = max(values, key=values.get)
        selected_score = float(values[selected_projection])
        selected_metrics = projection_scores[selected_projection]
        selected_probs = candidates[selected_projection]
        return (
            selected_projection,
            selected_probs,
            selected_score,
            projection_scores,
            selected_metrics,
        )

    def _measure_basis9(self, state: QState, shots: int) -> QutritMeasurementRecord:
        probabilities = np.abs(state.vector) ** 2
        probabilities = probabilities / probabilities.sum()
        candidates = self._projection_candidates_basis9(probabilities)
        (
            selected_projection,
            selected_probs,
            selected_projection_score,
            projection_scores,
            selected_metrics,
        ) = self._select_projection(candidates)
        sample_indices = self.rng.choice(9, size=shots, p=selected_probs)
        counts = np.bincount(sample_indices, minlength=9)
        frequencies = counts / float(shots)
        entropy = _shannon_entropy(frequencies)
        max_entropy = float(np.log(float(len(frequencies))))
        entropy_gap = max_entropy - entropy
        one_shot_entropies = []
        for index in sample_indices:
            one_hot = np.zeros(9, dtype=float)
            one_hot[index] = 1.0
            one_shot_entropies.append(_shannon_entropy(one_hot))
        variance = float(np.var(one_shot_entropies + [entropy]))
        labels = [f"{i}{j}" for i in range(3) for j in range(3)]
        datum = {label: float(value) for label, value in zip(labels, frequencies)}
        datum["projection_scores"] = projection_scores
        datum["selected_projection"] = selected_projection
        datum["selected_projection_score"] = selected_projection_score
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
            projection_scores=projection_scores,
            selected_projection=selected_projection,
            selected_projection_score=selected_projection_score,
            selection_rule="entropy_gap_projection_selection",
            observable_family="basis9_entropy",
            measurement_kind="qutrit_distribution_entropy_gap",
        )

    def _measure_motif27(self, state: QState, shots: int) -> QutritMeasurementRecord:
        if _v1._dashifine_map_27_to_H3x3 is None:
            raise RuntimeError("27->9 motif path requires dashifine map_27_to_H3x3")
        probabilities_27 = np.abs(state.vector) ** 2
        probabilities_27 = probabilities_27 / probabilities_27.sum()
        motif_probs = _v1._dashifine_map_27_to_H3x3.coarse9_from_weights27(probabilities_27)
        candidates = self._projection_candidates_motif9(motif_probs)
        (
            selected_projection,
            selected_probs,
            selected_projection_score,
            projection_scores,
            selected_metrics,
        ) = self._select_projection(candidates)
        sample_indices = self.rng.choice(9, size=shots, p=selected_probs)
        counts = np.bincount(sample_indices, minlength=9)
        frequencies = counts / float(shots)
        entropy = _shannon_entropy(frequencies)
        max_entropy = float(np.log(float(len(frequencies))))
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
            "selected_projection": selected_projection,
            "selected_projection_score": selected_projection_score,
            "projection_scores": projection_scores,
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
            projection_scores=projection_scores,
            selected_projection=selected_projection,
            selected_projection_score=selected_projection_score,
            selection_rule="entropy_gap_projection_selection",
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
        model = carrier.prep_metadata.get("triality_selection_model", "default")
        if model == "mdl":
            norms = [float(np.linalg.norm(vec)) for vec in self.planes.values()]
            mean_norm = float(np.mean(norms)) if norms else 1.0
            std_norm = float(np.std(norms)) if norms else 0.0
            symmetry_penalty = float(np.clip(std_norm / (mean_norm + 1e-9), 0.0, 1.0))
            self.mdl_penalty = symmetry_penalty
            strength_weight = 0.45
            stability_weight = 0.40
            symmetry_weight = 0.15 + 0.10 * (1.0 - symmetry_penalty)
            total_tmp = strength_weight + stability_weight + symmetry_weight
            default_weights = {
                "strength": strength_weight,
                "stability": stability_weight,
                "symmetry": symmetry_weight,
            }
        else:
            default_weights = {"strength": 0.5, "stability": 0.3, "symmetry": 0.2}
            self.mdl_penalty = 0.0
        user_weights = carrier.prep_metadata.get("triality_selection_weights", {})
        self.selection_model = model
        merged = {**default_weights, **user_weights}
        total = sum(max(v, 0.0) for v in merged.values())
        if total <= 0.0:
            merged = default_weights
            total = sum(merged.values())
        self.weights = {k: float(max(v, 0.0) / total) for k, v in merged.items()}
        self._eps = 1e-9

    def _reflection_from_plane(self, plane: np.ndarray) -> np.ndarray:
        vector = plane.astype(complex).reshape(-1)
        if vector.size == 0:
            raise ValueError("empty triality plane vector")
        if np.linalg.norm(vector) == 0:
            raise ValueError("triality plane vector has zero norm")
        vector = vector / np.linalg.norm(vector)
        projector = np.outer(vector, np.conj(vector))
        dimension = projector.shape[0]
        return 2.0 * projector - np.eye(dimension, dtype=complex)

    def _pair_correlation(self, state: QState, pair: tuple[int, int]) -> float:
        i, j = pair
        if i not in self.planes or j not in self.planes:
            raise ValueError(f"missing triality plane for pair {pair}")
        op_i = self._reflection_from_plane(self.planes[i])
        op_j = self._reflection_from_plane(self.planes[j])
        if op_i.shape[0] != 2 or op_j.shape[0] != 2:
            raise ValueError("triality selection expects 2D leg planes")
        op = _kron(op_i, op_j)
        if op.shape != (state.vector.shape[0], state.vector.shape[0]):
            raise ValueError(
                "triality pair operator dimension must match state dimension"
            )
        value = np.vdot(state.vector, op @ state.vector)
        return float(np.real(value))

    def _mdl_pair_terms(
        self,
        mean_corr: float,
        corr_var: float,
        symmetry: float,
    ) -> dict[str, float]:
        strength = float(np.clip(abs(mean_corr), self._eps, 1.0))
        stability = float(np.clip(np.exp(-corr_var), self._eps, 1.0))
        symmetry = float(np.clip(symmetry, self._eps, 1.0))
        signal_cost = float(-np.log(strength))
        stability_cost = float(-np.log(stability))
        symmetry_cost = float(-np.log(symmetry))
        mdl_cost = float(
            self.weights.get("strength", 0.0) * signal_cost
            + self.weights.get("stability", 0.0) * stability_cost
            + self.weights.get("symmetry", 0.0) * symmetry_cost
            + self.mdl_penalty
        )
        return {
            "strength": strength,
            "stability": stability,
            "symmetry": symmetry,
            "signal_cost": signal_cost,
            "stability_cost": stability_cost,
            "symmetry_cost": symmetry_cost,
            "mdl_cost": mdl_cost,
            "score": float(np.exp(-mdl_cost)),
        }

    def _score_pair(
        self,
        pair: tuple[int, int],
        mean_corr: float,
        corr_var: float,
        symmetry: float,
    ) -> dict[str, float]:
        _ = pair
        return self._mdl_pair_terms(mean_corr, corr_var, symmetry)

    def run(self, state: QState, shots: int) -> TrialityMeasurementRecord:
        if shots <= 0:
            raise ValueError("shots must be positive")
        pairs = ((0, 1), (0, 2), (1, 2))
        for pair in pairs:
            if pair[0] not in self.planes or pair[1] not in self.planes:
                raise ValueError(f"missing plane for triality pair {pair}")

        norms = {idx: float(np.linalg.norm(vec)) for idx, vec in self.planes.items()}
        if not norms:
            raise ValueError("triality planes are empty")
        max_norm = max(norms.values())
        sym_scale = max_norm if max_norm > 0 else 1.0

        rng = np.random.default_rng()
        samples: list[dict[tuple[int, int], float]] = []
        noises = []
        jitter = 1e-4

        for _ in range(shots):
            # state perturbation is small and purely stochastic,
            # giving a stability estimate for selection.
            noise = (rng.normal(0.0, jitter, size=state.vector.size) +
                     1j * rng.normal(0.0, jitter, size=state.vector.size))
            perturbed = state.vector + noise
            perturbed = QState(perturbed, basis=state.basis, metadata=state.metadata)
            sample: dict[tuple[int, int], float] = {}
            for pair in pairs:
                sample[pair] = float(np.clip(self._pair_correlation(perturbed, pair), -1.0, 1.0))
            noises.append(noise)
            samples.append(sample)

        pair_data: dict[tuple[int, int], dict[str, float]] = {}
        for pair in pairs:
            values = [sample[pair] for sample in samples]
            mean_corr = float(np.mean(values))
            corr_var = float(np.var(values))
            norm_diff = abs(norms[pair[0]] - norms[pair[1]]) / sym_scale
            symmetry = 1.0 - norm_diff
            mdl_terms = self._score_pair(pair, mean_corr, corr_var, symmetry)
            pair_data[pair] = {
                "correlation": mean_corr,
                "variance": corr_var,
                "stability": mdl_terms["stability"],
                "symmetry": symmetry,
                "strength": mdl_terms["strength"],
                "signal_cost": mdl_terms["signal_cost"],
                "stability_cost": mdl_terms["stability_cost"],
                "symmetry_cost": mdl_terms["symmetry_cost"],
                "mdl_cost": mdl_terms["mdl_cost"],
                "score": mdl_terms["score"],
            }

        selected_pair = max(pair_data, key=lambda pair: pair_data[pair]["score"])
        selected = pair_data[selected_pair]
        correlation = selected["correlation"]
        variance = selected["variance"]
        selected_pair_score = selected["score"]
        pair_scores = {
            f"{i}{j}": {
                "correlation": values["correlation"],
                "variance": values["variance"],
                "strength": values["strength"],
                "stability": values["stability"],
                "symmetry": values["symmetry"],
                "signal_cost": values["signal_cost"],
                "stability_cost": values["stability_cost"],
                "symmetry_cost": values["symmetry_cost"],
                "mdl_cost": values["mdl_cost"],
                "score": values["score"],
            }
            for (i, j), values in pair_data.items()
        }

        return TrialityMeasurementRecord(
            datum={
                "selected_pair": list(selected_pair),
                "pair_scores": pair_scores,
                "selection_weights": self.weights,
                "selection_model": self.selection_model,
                "mdl_penalty": self.mdl_penalty,
                "shots_states": {
                    "state_norm": float(np.linalg.norm(state.vector)),
                    "jitter_norm_mean": float(np.mean(np.linalg.norm(noises, axis=1))),
                    "jitter_norm_std": float(np.std(np.linalg.norm(noises, axis=1))),
                },
            },
            projected_state=_project(state, "triality_pair_measurement"),
            selected_pair=selected_pair,
            correlation=correlation,
            selected_pair_score=selected_pair_score,
            shots=shots,
            variance=variance,
            pair_scores=pair_scores,
            selection_rule=(
                "mdl_pair_selection"
                if self.selection_model == "mdl"
                else "multi_criterion_pair_selection"
            ),
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
    def __init__(
        self,
        entropy_var_threshold: float = 0.02,
        min_entropy_gap: float = 0.10,
        min_projection_score: float = 0.25,
        motif_entropy_var_threshold: float = 0.05,
        motif_min_entropy_gap: float = 0.05,
    ):
        self.entropy_var_threshold = entropy_var_threshold
        self.min_entropy_gap = min_entropy_gap
        self.min_projection_score = min_projection_score
        self.motif_entropy_var_threshold = motif_entropy_var_threshold
        self.motif_min_entropy_gap = motif_min_entropy_gap

    def decide(self, record: QutritMeasurementRecord) -> PromotionResult:
        datum = dict(record.datum)
        datum["entropy"] = record.entropy
        datum["entropy_gap"] = record.entropy_gap
        datum["selected_projection"] = record.selected_projection
        datum["selected_projection_score"] = record.selected_projection_score
        if record.observable_family == "motif9_entropy":
            if record.variance > self.motif_entropy_var_threshold:
                return PromotionResult(False, "high_entropy_variance_motif", datum)
            if record.selected_projection_score < self.min_projection_score:
                return PromotionResult(False, "weak_projection_selection_motif", datum)
            if record.entropy_gap > self.motif_min_entropy_gap:
                return PromotionResult(True, "structured_qutrit_motif_distribution", datum)
            return PromotionResult(False, "near_uniform_qutrit_motif_distribution", datum)
        # basis9 path
        if record.variance > self.entropy_var_threshold:
            return PromotionResult(False, "high_entropy_variance", datum)
        if record.selected_projection_score < self.min_projection_score:
            return PromotionResult(False, "weak_projection_selection", datum)
        if record.entropy_gap > self.min_entropy_gap:
            return PromotionResult(True, "structured_qutrit_distribution", datum)
        return PromotionResult(False, "near_uniform_qutrit_distribution", datum)


class TrialityPromotion:
    def __init__(
        self,
        corr_threshold: float = 0.5,
        var_threshold: float = 0.05,
        score_threshold: float = 0.45,
    ):
        self.corr_threshold = corr_threshold
        self.var_threshold = var_threshold
        self.score_threshold = score_threshold

    def decide(self, record: TrialityMeasurementRecord) -> PromotionResult:
        score = float(record.selected_pair_score)
        if score < self.score_threshold:
            return PromotionResult(False, "low_selection_score", record.datum)
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
            "selection": {
                "rule": record.selection_rule,
                "selected_projection": record.selected_projection,
                "selected_projection_score": record.selected_projection_score,
                "projection_scores": record.projection_scores,
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
        elif (
            carrier.prep_metadata.get("qg_dynamics_metadata") is not None
            or carrier.prep_metadata.get("qg_mdl_metadata") is not None
        ):
            witness["agda_reference"] = {
                "selected_model": carrier.prep_metadata.get("motif_model"),
                "comparison_models": carrier.prep_metadata.get("motif_compare_models"),
                "qg_dynamics": carrier.prep_metadata.get("qg_dynamics_metadata"),
                "qg_mdl_prior": carrier.prep_metadata.get("qg_mdl_metadata"),
                "replacement_policy": (
                    carrier.prep_metadata.get("qg_model_comparison", {}).get("replacement_policy")
                    if carrier.prep_metadata.get("qg_model_comparison") is not None
                    else None
                ),
                "ranking": (
                    carrier.prep_metadata.get("qg_model_comparison", {}).get("ranking")
                    if carrier.prep_metadata.get("qg_model_comparison") is not None
                    else None
                ),
                "model_outputs": (
                    carrier.prep_metadata.get("qg_model_comparison", {}).get("model_outputs")
                    if carrier.prep_metadata.get("qg_model_comparison") is not None
                    else None
                ),
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
                "rule": record.selection_rule,
                "selected_pair_score": record.selected_pair_score,
                "pair_scores": record.datum.get("pair_scores"),
                "selection_weights": record.datum.get("selection_weights"),
                "selection_model": record.datum.get("selection_model"),
                "mdl_penalty": record.datum.get("mdl_penalty"),
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
        return float(-np.log1p(record.variance) - deviation)
    if carrier_type == CarrierType.QUTRIT:
        score_term = -np.log(max(record.selected_projection_score, 1e-12))
        entropy_term = record.entropy / max(record.entropy_gap + record.entropy, 1e-9)
        return float(-(score_term + entropy_term))
    if carrier_type == CarrierType.TRIALITY:
        mdl_cost = float(
            record.pair_scores[f"{record.selected_pair[0]}{record.selected_pair[1]}"]["mdl_cost"]
        )
        return float(-(mdl_cost) - abs(record.correlation))
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


def write_comparison_artifact() -> None:
    job_motif = prepare_qutrit_motif27_job()
    out_motif = run_typed_pipeline(job_motif, shots=128)
    ref = out_motif["witness"].get("agda_reference", {})

    job_basis = prepare_qutrit_planes_job()
    out_basis = run_typed_pipeline(job_basis, shots=128)

    job_triality = prepare_triality_job()
    out_triality = run_typed_pipeline(job_triality, shots=128)

    artifact = {
        "selected_model": ref.get("replacement_policy", {}).get("decision"),
        "replacement_policy": ref.get("replacement_policy"),
        "ranking": ref.get("ranking"),
        "model_outputs": ref.get("model_outputs"),
        "comparison_models": ref.get("comparison_models"),
        "observables": {
            "qutrit_motif27": {
                "promotion": out_motif["promotion"]._asdict() if hasattr(out_motif["promotion"], "_asdict") else str(out_motif["promotion"]),
                "observable": out_motif["record"].entropy_gap if hasattr(out_motif["record"], "entropy_gap") else None,
                "gap": out_motif["gap"],
            },
            "qutrit_planes": {
                "promotion": out_basis["promotion"]._asdict() if hasattr(out_basis["promotion"], "_asdict") else str(out_basis["promotion"]),
                "observable": out_basis["record"].entropy_gap if hasattr(out_basis["record"], "entropy_gap") else None,
                "gap": out_basis["gap"],
            },
            "triality_frames": {
                "promotion": out_triality["promotion"]._asdict() if hasattr(out_triality["promotion"], "_asdict") else str(out_triality["promotion"]),
                "observable": out_triality["record"].correlation if hasattr(out_triality["record"], "correlation") else None,
                "gap": out_triality["gap"],
            },
        },
    }

    timestamp = _dt.datetime.now().strftime("%Y%m%d")
    path = Path(f"gpt_experiments/qg_motif_comparison_multi_{timestamp}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True))
    print(f"wrote comparison artifact to {path}")


def _kron(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.kron(a, b)


def _qutrit_phase_rotation() -> UnitaryOp:
    z = _v1._dashifine_ternary_hilbert.Z_qutrit()
    return UnitaryOp(_kron(z, z), name="qutrit_phase_rotation")


def _triality_context_for_qg(theta: float = 0.3, shots: int = 64) -> dict[str, Any]:
    u_a, u_b, params = _v1._extract_triality_planes()
    psi = _v1._dashifine_chsh_harness.two_qubit_from_two_local_planes(u_a, u_b)
    carrier = CarrierSpec(
        carrier_type=CarrierType.TRIALITY,
        name="triality_frames",
        dimension=4,
        prep_metadata={
            "source": (
                "dashifine.newtest.triality_stack.build_triality_stack_H + "
                "dashifine.newtest.chsh_harness.extract_local_plane_basis_at_wall + "
                "dashifine.newtest.chsh_harness.two_qubit_from_two_local_planes"
            ),
            "triality_selection_model": "mdl",
            **params,
        },
    )
    state = QState(psi, metadata={"prepared_by": "triality_frames"})
    evolved = UnitaryOp(_v1.j_rotation(theta).U, name="J_rotation").step(state)
    record = TrialityMeasurement(carrier).run(evolved, shots=shots)
    pair_key = f"{record.selected_pair[0]}{record.selected_pair[1]}"
    pair_info = record.pair_scores[pair_key]
    return {
        "selected_pair": list(record.selected_pair),
        "pair_bias": float(record.selected_pair_score),
        "mdl_cost": float(pair_info["mdl_cost"]),
        "correlation": float(record.correlation),
        "selection_model": record.datum.get("selection_model"),
        "selection_weights": record.datum.get("selection_weights"),
        "source_params": params,
    }


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
            "triality_selection_model": "mdl",
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
    carrier_pref = {
        "motif_model": "qg_dynamics",
        "motif_compare_models": [
            "qg_mdl",
            "qg_large_tail",
            "qg_large_tail_v2",
            "qg_ensemble",
            "qg_projection_covariant",
            "qg_triality_coupled",
            "qg_ccr_experimental",
        ],
    }
    triplets = ((0, 1, 2), (1, 1, 1), (0, 0, 1))
    amplitudes = np.array([0.62, 0.56, 0.55], dtype=complex)
    base = sum(
        amp * _v1._dashifine_map_27_to_H3x3.triplet_ket(i, j, k)
        for amp, (i, j, k) in zip(amplitudes, triplets)
    )
    weights_override = None
    motif_source = "triplet_seed"
    qg_metadata: dict[str, Any] | None = None
    qg_dynamics_metadata: dict[str, Any] | None = None
    qg_comparison: dict[str, Any] | None = None
    model_config: dict[str, Any] = {}
    if hasattr(_v1._dashifine_map_27_to_H3x3, "motif_weights27_default"):
        try:
            weights_override = _v1._dashifine_map_27_to_H3x3.motif_weights27_default()
            motif_source = "dashifine_default_weights"
        except Exception:
            weights_override = None
            motif_source = "triplet_seed"
    if weights_override is None and hasattr(_v1._dashifine_map_27_to_H3x3, "motif_weights27_curated"):
        try:
            weights_override = _v1._dashifine_map_27_to_H3x3.motif_weights27_curated()
            motif_source = "dashifine_curated_weights"
        except Exception:
            weights_override = None
            motif_source = "triplet_seed"
    motif_model = carrier_pref.get("motif_model", "qg_dynamics")
    compare_models = list(carrier_pref.get("motif_compare_models", []))
    if motif_model == "qg_triality_coupled":
        model_config["triality_context"] = _triality_context_for_qg()
    elif "qg_triality_coupled" in compare_models:
        model_config["triality_context"] = _triality_context_for_qg()

    probabilities_pref = carrier_pref.get("motif_preset", motif_model)
    if weights_override is not None:
        probabilities_27 = weights_override
    elif probabilities_pref == "uniform27_mdl":
        probabilities_27 = np.ones(27, float) / 27.0
        motif_source = "uniform27_mdl_preset"
    elif probabilities_pref == "structured27_curated":
        # reuse the earlier triplet mix as a structured preset
        structured = np.abs(base) ** 2
        probabilities_27 = _v1._dashifine_map_27_to_H3x3.mix_over_27(structured)
        motif_source = "structured27_curated"
    else:
        selected_model = _qg_models.build_model(motif_model, config=model_config)
        qg_comparison = _qg_models.build_comparison(motif_model, compare_models, config=model_config)
        probabilities_27 = selected_model.weights27
        motif_source = f"{motif_model}_agda_semantics"
        if motif_model == "qg_mdl":
            qg_metadata = selected_model.metadata
        elif motif_model == "qg_dynamics":
            qg_dynamics_metadata = selected_model.metadata
            if "qg_mdl" in qg_comparison["model_outputs"]:
                qg_metadata = qg_comparison["model_outputs"]["qg_mdl"]["metadata"]
        else:
            if "qg_mdl" in qg_comparison["model_outputs"]:
                qg_metadata = qg_comparison["model_outputs"]["qg_mdl"]["metadata"]
            if "qg_dynamics" in qg_comparison["model_outputs"]:
                qg_dynamics_metadata = qg_comparison["model_outputs"]["qg_dynamics"]["metadata"]
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
                "motif_source": motif_source,
                "motif_preset": probabilities_pref,
                "motif_model": motif_model,
                "motif_compare_models": compare_models,
                "qg_mdl_metadata": qg_metadata,
                "qg_dynamics_metadata": qg_dynamics_metadata,
                "qg_model_comparison": qg_comparison,
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
    write_comparison_artifact()


if __name__ == "__main__":
    demo()
