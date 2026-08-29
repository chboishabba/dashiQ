"""CHSH-specific BIDI receipt for the dashiQ qubit carrier.

The generic experiment receipt keeps runtime promotion below theory promotion.
This module goes one step more literal for the qubit path already implemented in
`computer_v2.py`: it reads the CHSH observable, the classical bound recorded in
the witness, and the variance criterion, then classifies the finite runtime
outcome for the Agda `QuantumCHSHDiscriminatorExact` consumer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from experiment_receipt import PromotionCriterionReceipt


@dataclass(frozen=True)
class CHSHDiscriminatorReceipt:
    observable: float
    classical_bound: float
    variance: float
    variance_threshold: float
    shots: int
    criterion: PromotionCriterionReceipt
    runtime_accepted: bool
    runtime_reason: str
    classified_outcome: str
    criterion_predeclared: bool
    variance_criterion_satisfied: bool
    finite_experiment_only: bool = True
    splits_classical_bounded_candidate_if_violation: bool = True
    establishes_quantum_gravity: bool = False
    discharges_physical_promotion_gate: bool = False

    @property
    def eligible_discriminator_evidence(self) -> bool:
        return bool(
            self.criterion_predeclared
            and self.variance_criterion_satisfied
            and self.classified_outcome == "violates_classical_bound"
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["eligible_discriminator_evidence"] = self.eligible_discriminator_evidence
        return result


def build_chsh_discriminator_receipt(
    *,
    measurement_record: Any,
    promotion_result: Any,
    witness: dict[str, Any],
    criterion: PromotionCriterionReceipt,
) -> CHSHDiscriminatorReceipt:
    observable = float(getattr(measurement_record, "observable"))
    variance = float(getattr(measurement_record, "variance"))
    shots = int(getattr(measurement_record, "shots"))

    observable_meta = dict(witness.get("observable", {}))
    bounds = dict(observable_meta.get("bounds", {}))
    classical_bound = float(bounds.get("classical", 2.0))

    threshold_meta = dict(criterion.threshold_metadata)
    declared_bound = float(threshold_meta.get("classical_bound", classical_bound))
    if declared_bound != classical_bound:
        raise ValueError(
            "predeclared classical bound does not match the bound carried by the runtime witness"
        )

    variance_threshold = float(threshold_meta["variance_threshold"])
    variance_ok = variance <= variance_threshold
    outcome = (
        "violates_classical_bound"
        if abs(observable) > classical_bound
        else "within_classical_bound"
    )

    return CHSHDiscriminatorReceipt(
        observable=observable,
        classical_bound=classical_bound,
        variance=variance,
        variance_threshold=variance_threshold,
        shots=shots,
        criterion=criterion,
        runtime_accepted=bool(getattr(promotion_result, "accepted")),
        runtime_reason=str(getattr(promotion_result, "reason")),
        classified_outcome=outcome,
        criterion_predeclared=criterion.declared_before_measurement,
        variance_criterion_satisfied=variance_ok,
    )
