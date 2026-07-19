"""Focused tests for the computer-v3 MDL governance seam.

These tests use synthetic measurement records, so they validate the evidence and
promotion logic without requiring the optional dashifine preparation paths.
"""

from __future__ import annotations

import unittest

import numpy as np

import computer_v2 as v2
import computer_v3 as v3


class ComputerV3MDLTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projected4 = v2.QState(np.array([1.0, 0.0, 0.0, 0.0], dtype=complex))
        self.projected9 = v2.QState(
            np.array([1.0] + [0.0] * 8, dtype=complex)
        )

    def test_qubit_strong_chsh_can_clear_mdl(self) -> None:
        record = v2.QubitMeasurementRecord(
            datum={"S": 2.8},
            projected_state=self.projected4,
            observable=2.8,
            shots=1000,
            variance=1.0e-4,
        )
        ledger = v3.mdl_evidence_ledger(record, v2.CarrierType.QUBIT)
        self.assertGreater(ledger.evidence_gain, 0.0)
        self.assertTrue(ledger.sufficient)

    def test_qubit_classical_value_is_blocked(self) -> None:
        record = v2.QubitMeasurementRecord(
            datum={"S": 1.9},
            projected_state=self.projected4,
            observable=1.9,
            shots=1000,
            variance=1.0e-4,
        )
        ledger = v3.mdl_evidence_ledger(record, v2.CarrierType.QUBIT)
        self.assertFalse(ledger.sufficient)
        self.assertGreater(ledger.promotability_gap, 0.0)

    def test_qutrit_structured_distribution_beats_uniform_null(self) -> None:
        probs = np.array([0.9] + [0.1 / 8.0] * 8, dtype=float)
        entropy = float(-np.sum(probs * np.log(probs)))
        record = v2.QutritMeasurementRecord(
            datum={"probabilities": probs.tolist()},
            projected_state=self.projected9,
            probs=probs,
            entropy=entropy,
            entropy_gap=float(np.log(9.0) - entropy),
            shots=1000,
            variance=1.0e-4,
            projection_scores={
                "identity": {"score": 1.0},
                "roll1": {"score": 0.5},
                "roll2": {"score": 0.4},
            },
            selected_projection="identity",
            selected_projection_score=1.0,
            observable_family="motif9_entropy",
            measurement_kind="qutrit_motif_distribution",
        )
        ledger = v3.mdl_evidence_ledger(record, v2.CarrierType.QUTRIT)
        self.assertGreater(ledger.evidence_gain, 0.0)
        self.assertTrue(ledger.sufficient)

    def test_qutrit_uniform_distribution_is_blocked_by_model_cost(self) -> None:
        probs = np.full(9, 1.0 / 9.0, dtype=float)
        record = v2.QutritMeasurementRecord(
            datum={"probabilities": probs.tolist()},
            projected_state=self.projected9,
            probs=probs,
            entropy=float(np.log(9.0)),
            entropy_gap=0.0,
            shots=1000,
            variance=0.0,
            projection_scores={"identity": {"score": 0.0}},
            selected_projection="identity",
            selected_projection_score=0.0,
            observable_family="motif9_entropy",
            measurement_kind="qutrit_motif_distribution",
        )
        ledger = v3.mdl_evidence_ledger(record, v2.CarrierType.QUTRIT)
        self.assertLess(ledger.evidence_gain, 0.0)
        self.assertFalse(ledger.sufficient)

    def test_triality_selection_cost_is_audited(self) -> None:
        record = v2.TrialityMeasurementRecord(
            datum={"selection_model": "mdl"},
            projected_state=self.projected4,
            selected_pair=(0, 1),
            correlation=0.95,
            selected_pair_score=0.9,
            shots=1000,
            variance=1.0e-4,
            pair_scores={
                "01": {"mdl_cost": 0.2},
                "02": {"mdl_cost": 1.1},
                "12": {"mdl_cost": 1.3},
            },
        )
        ledger = v3.mdl_evidence_ledger(record, v2.CarrierType.TRIALITY)
        self.assertAlmostEqual(ledger.terms["pair_candidates"], 3.0)
        self.assertAlmostEqual(ledger.terms["intrinsic_pair_mdl_cost"], 0.2)
        self.assertTrue(ledger.sufficient)

    def test_governance_requires_candidate_and_mdl(self) -> None:
        record = v2.QubitMeasurementRecord(
            datum={"S": 2.8},
            projected_state=self.projected4,
            observable=2.8,
            shots=1000,
            variance=1.0e-4,
        )
        ledger = v3.mdl_evidence_ledger(record, v2.CarrierType.QUBIT)
        candidate_reject = v2.PromotionResult(False, "carrier_gate", {"S": 2.8})
        governed = v3.govern_candidate_promotion(candidate_reject, ledger)
        self.assertFalse(governed.accepted)
        self.assertTrue(governed.reason.startswith("candidate_rejected:"))


if __name__ == "__main__":
    unittest.main()
