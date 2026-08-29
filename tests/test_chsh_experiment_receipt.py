from __future__ import annotations

from dataclasses import dataclass

from chsh_experiment_receipt import build_chsh_discriminator_receipt
from experiment_receipt import PromotionCriterionReceipt


@dataclass
class Record:
    observable: float
    variance: float
    shots: int


@dataclass
class Promotion:
    accepted: bool
    reason: str


def criterion(predeclared: bool) -> PromotionCriterionReceipt:
    return PromotionCriterionReceipt(
        name="chsh_classical_bound",
        declared_before_measurement=predeclared,
        justification="classical CHSH discriminator",
        threshold_metadata={"classical_bound": 2.0, "variance_threshold": 0.05},
    )


def witness() -> dict:
    return {"observable": {"bounds": {"classical": 2.0}}}


def test_predeclared_low_variance_violation_is_eligible_discriminator_evidence() -> None:
    receipt = build_chsh_discriminator_receipt(
        measurement_record=Record(observable=2.4, variance=0.01, shots=4096),
        promotion_result=Promotion(accepted=True, reason="nonlocal_signal"),
        witness=witness(),
        criterion=criterion(True),
    )
    assert receipt.classified_outcome == "violates_classical_bound"
    assert receipt.eligible_discriminator_evidence is True
    assert receipt.establishes_quantum_gravity is False
    assert receipt.discharges_physical_promotion_gate is False


def test_posthoc_violation_is_not_independent_discriminator_evidence() -> None:
    receipt = build_chsh_discriminator_receipt(
        measurement_record=Record(observable=2.4, variance=0.01, shots=4096),
        promotion_result=Promotion(accepted=True, reason="nonlocal_signal"),
        witness=witness(),
        criterion=criterion(False),
    )
    assert receipt.eligible_discriminator_evidence is False


def test_high_variance_violation_fails_receipt_even_if_runtime_flag_is_true() -> None:
    receipt = build_chsh_discriminator_receipt(
        measurement_record=Record(observable=2.4, variance=0.20, shots=64),
        promotion_result=Promotion(accepted=True, reason="synthetic"),
        witness=witness(),
        criterion=criterion(True),
    )
    assert receipt.variance_criterion_satisfied is False
    assert receipt.eligible_discriminator_evidence is False
