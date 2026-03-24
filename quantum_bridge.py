"""Minimal quantum bridge skeleton for dashiQ.

This module keeps the critical seam explicit:

- unitary evolution acts on latent quantum state
- measurement produces classical evidence
- promotion is a later governance decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, sin
from typing import Any, Mapping, Protocol


def _normalize_amplitudes(amplitudes: tuple[complex, ...]) -> tuple[complex, ...]:
    norm_sq = sum(abs(value) ** 2 for value in amplitudes)
    if norm_sq <= 0.0:
        raise ValueError("quantum state must have nonzero norm")
    scale = norm_sq ** 0.5
    return tuple(value / scale for value in amplitudes)


@dataclass(frozen=True)
class QState:
    """Latent non-canonical quantum-like state."""

    amplitudes: tuple[complex, ...]
    basis: str = "computational"
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = _normalize_amplitudes(self.amplitudes)
        object.__setattr__(self, "amplitudes", normalized)

    @property
    def dimension(self) -> int:
        return len(self.amplitudes)

    def probabilities(self) -> tuple[float, ...]:
        return tuple(abs(value) ** 2 for value in self.amplitudes)


class UnitaryOp(Protocol):
    name: str

    def apply(self, state: QState) -> QState: ...

    def inverse(self) -> "UnitaryOp": ...


class Observable(Protocol):
    name: str

    def evaluate(self, state: QState) -> float | complex | dict[str, float]: ...


class MeasurementOp(Protocol):
    name: str

    def project(self, state: QState) -> QState: ...

    def measure(self, state: QState) -> "MeasurementRecord": ...


@dataclass(frozen=True)
class MeasurementRecord:
    """First classical evidence object emitted by the bridge."""

    measurement: str
    basis: str
    outcome: str
    probabilities: Mapping[str, float]
    witness: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromotionPolicy:
    """Simple governance rule for promoting measured outputs."""

    name: str
    min_confidence: float = 0.90
    require_basis_match: bool = True

    def evaluate(self, record: MeasurementRecord, state: QState) -> "PromotionResult":
        confidence = max(record.probabilities.values(), default=0.0)
        reasons: list[str] = []

        if self.require_basis_match and record.basis != state.basis:
            reasons.append("measurement basis does not match latent state basis")
        if confidence < self.min_confidence:
            reasons.append(
                f"confidence {confidence:.3f} is below threshold {self.min_confidence:.3f}"
            )

        promoted = not reasons
        status = "promoted" if promoted else "candidate_only"
        return PromotionResult(
            policy=self.name,
            status=status,
            promoted=promoted,
            confidence=confidence,
            reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class PromotionResult:
    policy: str
    status: str
    promoted: bool
    confidence: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class WitnessStatus:
    """Tiny FRACDASH-style status surface for the bridge."""

    carrier_family: str
    evolution_claim: str
    projection_claim: str
    observable_claim: str


@dataclass(frozen=True)
class QuantumRunResult:
    final_state: QState
    measurement: MeasurementRecord
    promotion: PromotionResult
    observables: Mapping[str, float | complex | dict[str, float]]
    witness_status: WitnessStatus


@dataclass(frozen=True)
class Rotation2D:
    """Toy reversible operator on a real 2-plane embedded in complex amplitudes."""

    theta: float
    name: str = "rotation_2d"

    def apply(self, state: QState) -> QState:
        if state.dimension != 2:
            raise ValueError("Rotation2D expects a 2D state")
        a0, a1 = state.amplitudes
        c = cos(self.theta)
        s = sin(self.theta)
        rotated = (c * a0 - s * a1, s * a0 + c * a1)
        provenance = dict(state.provenance)
        provenance["last_unitary"] = self.name
        provenance["theta"] = self.theta
        return QState(rotated, basis=state.basis, provenance=provenance)

    def inverse(self) -> "Rotation2D":
        return Rotation2D(theta=-self.theta, name=f"{self.name}_inv")


@dataclass(frozen=True)
class ComputationalBasisMeasurement:
    name: str = "computational_measurement"

    def project(self, state: QState) -> QState:
        probabilities = state.probabilities()
        winner = max(range(len(probabilities)), key=probabilities.__getitem__)
        collapsed = tuple(
            1.0 + 0.0j if index == winner else 0.0 + 0.0j
            for index in range(state.dimension)
        )
        provenance = dict(state.provenance)
        provenance["projected_by"] = self.name
        provenance["projected_outcome"] = str(winner)
        return QState(collapsed, basis=state.basis, provenance=provenance)

    def measure(self, state: QState) -> MeasurementRecord:
        probabilities = state.probabilities()
        labels = {str(index): value for index, value in enumerate(probabilities)}
        outcome = max(labels, key=labels.__getitem__)
        return MeasurementRecord(
            measurement=self.name,
            basis=state.basis,
            outcome=outcome,
            probabilities=labels,
            witness={
                "measurement_kind": "max_probability_readout",
                "project_is_idempotent_by_construction": True,
            },
        )


@dataclass(frozen=True)
class PopulationObservable:
    """Simple observable exposing basis-state populations."""

    name: str = "population"

    def evaluate(self, state: QState) -> dict[str, float]:
        return {
            str(index): probability
            for index, probability in enumerate(state.probabilities())
        }


def prepare_qubit(alpha: complex, beta: complex, basis: str = "computational") -> QState:
    return QState((alpha, beta), basis=basis, provenance={"prepared_by": "prepare_qubit"})


def run_quantum_pipeline(
    initial_state: QState,
    evolutions: tuple[UnitaryOp, ...],
    measurement: MeasurementOp,
    promotion_policy: PromotionPolicy,
    observables: tuple[Observable, ...] = (),
) -> QuantumRunResult:
    state = initial_state
    for op in evolutions:
        state = op.apply(state)

    measurement_record = measurement.measure(state)
    promotion_result = promotion_policy.evaluate(measurement_record, state)
    observable_payload = {
        observable.name: observable.evaluate(state) for observable in observables
    }

    return QuantumRunResult(
        final_state=state,
        measurement=measurement_record,
        promotion=promotion_result,
        observables=observable_payload,
        witness_status=WitnessStatus(
            carrier_family="finite_statevector_2d",
            evolution_claim="exact_reversible_rotation_in_toy_model",
            projection_claim="computational_basis_projection_idempotent_by_construction",
            observable_claim="population_report_exact_for_current_toy_carrier",
        ),
    )
