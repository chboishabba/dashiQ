"""BIDI experiment receipts for dashiQ carrier-specific runtime promotions.

`computer_v2` already separates carrier type, measurement, promotion strategy
and witness construction.  This adapter keeps runtime acceptance below the
physical-theory promotion boundary and records criterion provenance explicitly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PromotionCriterionReceipt:
    name: str
    declared_before_measurement: bool
    justification: str
    threshold_metadata: dict[str, Any]


@dataclass(frozen=True)
class QuantumExperimentReceipt:
    carrier: str
    measurement_kind: str
    accepted_by_runtime_rule: bool
    runtime_reason: str
    measurement_datum: dict[str, Any]
    witness: dict[str, Any]
    criterion: PromotionCriterionReceipt | None
    finite_experiment_only: bool = True
    runtime_acceptance_is_established_theory: bool = False
    selection_score_is_falsifiable_observable_by_default: bool = False
    experiment_receipt_still_needs_physical_promotion_gate: bool = True

    @property
    def criterion_predeclared(self) -> bool:
        return bool(
            self.criterion is not None
            and self.criterion.declared_before_measurement
        )

    @property
    def eligible_as_experiment_evidence(self) -> bool:
        return bool(
            self.accepted_by_runtime_rule
            and self.criterion_predeclared
            and bool(self.witness)
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["criterion_predeclared"] = self.criterion_predeclared
        data["eligible_as_experiment_evidence"] = self.eligible_as_experiment_evidence
        return data


def build_quantum_experiment_receipt(
    *,
    carrier: Any,
    measurement_record: Any,
    promotion_result: Any,
    witness: dict[str, Any],
    criterion: PromotionCriterionReceipt | None = None,
) -> QuantumExperimentReceipt:
    """Package existing computer_v2 outputs without strengthening the claim.

    The function intentionally accepts the runtime objects by protocol rather
    than importing `computer_v2`, so it cannot introduce a circular dependency.
    It expects the public attributes already exposed by that module.
    """

    carrier_value = getattr(carrier, "carrier_type", carrier)
    carrier_value = getattr(carrier_value, "value", str(carrier_value))
    measurement_kind = str(
        getattr(measurement_record, "measurement_kind", type(measurement_record).__name__)
    )
    datum = dict(getattr(promotion_result, "datum", {}))
    return QuantumExperimentReceipt(
        carrier=str(carrier_value),
        measurement_kind=measurement_kind,
        accepted_by_runtime_rule=bool(getattr(promotion_result, "accepted")),
        runtime_reason=str(getattr(promotion_result, "reason")),
        measurement_datum=datum,
        witness=dict(witness),
        criterion=criterion,
    )
