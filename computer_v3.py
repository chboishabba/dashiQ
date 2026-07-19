"""MDL-governed promotion layer for the typed dashiQ computer.

`computer_v2` remains the carrier-native execution engine.  This module adds a
shared evidence/code-length ledger after measurement:

    latent state -> reversible evolution -> carrier-native measurement
    -> v2 candidate promotion -> MDL evidence ledger -> DASHI promotion

The common quantity is not a score on raw amplitudes.  It is the code-length
advantage of a structured explanation over a carrier-appropriate null model.
A result is promoted only when both the v2 carrier policy and the MDL policy
accept it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

import computer_v2 as v2


_EPS = 1.0e-12


@dataclass(frozen=True)
class MDLEvidenceLedger:
    carrier: str
    null_model: str
    structured_model: str
    null_code_length: float
    structured_code_length: float
    model_code_length: float
    selection_code_length: float
    evidence_gain: float
    minimum_gain: float
    promotability_gap: float
    sufficient: bool
    terms: dict[str, float]
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class GovernedPromotionResult:
    accepted: bool
    reason: str
    candidate_promotion: v2.PromotionResult
    mdl_evidence: MDLEvidenceLedger
    datum: dict[str, Any]


def _safe_log(value: float) -> float:
    return math.log(max(float(value), _EPS))


def _normal_sigma(variance: float, shots: int) -> float:
    """Conservative standard error floor for expectation-like observables."""

    return math.sqrt(max(float(variance), 0.0) + 1.0 / max(int(shots), 1))


def _qubit_ledger(
    record: v2.QubitMeasurementRecord,
    minimum_gain: float,
) -> MDLEvidenceLedger:
    # Null: a classical CHSH model can account for |S| <= 2.
    excess = max(0.0, abs(float(record.observable)) - 2.0)
    sigma = _normal_sigma(record.variance, record.shots)
    z = excess / sigma
    null_data_cost = 0.5 * z * z

    # Structured model pays for one effect-size parameter and the named CHSH
    # measurement family.  The residual cost is zero at this summary level.
    parameter_cost = 0.5 * _safe_log(record.shots + 1.0)
    family_cost = _safe_log(2.0)
    model_cost = parameter_cost + family_cost
    structured_data_cost = 0.0
    structured_total = structured_data_cost + model_cost
    gain = null_data_cost - structured_total
    gap = minimum_gain - gain

    return MDLEvidenceLedger(
        carrier=v2.CarrierType.QUBIT.value,
        null_model="classical_CHSH_bound",
        structured_model="one_parameter_CHSH_excess",
        null_code_length=float(null_data_cost),
        structured_code_length=float(structured_total),
        model_code_length=float(model_cost),
        selection_code_length=float(family_cost),
        evidence_gain=float(gain),
        minimum_gain=float(minimum_gain),
        promotability_gap=float(gap),
        sufficient=bool(gap <= 0.0 and excess > 0.0),
        terms={
            "chsh_abs": abs(float(record.observable)),
            "classical_bound": 2.0,
            "excess": excess,
            "standard_error": sigma,
            "z_excess": z,
            "parameter_cost": parameter_cost,
        },
        assumptions=(
            "CHSH expectation is summarized by an approximately normal error scale",
            "the structured alternative adds one effect-size parameter",
            "raw amplitudes are not scored or promoted",
        ),
    )


def _qutrit_ledger(
    record: v2.QutritMeasurementRecord,
    minimum_gain: float,
) -> MDLEvidenceLedger:
    probs = np.asarray(record.probs, dtype=float)
    probs = probs / max(float(np.sum(probs)), _EPS)
    support = max(int(np.count_nonzero(probs > _EPS)), 1)
    shots = max(int(record.shots), 1)

    # Null: uniform categorical distribution on the measured support.
    null_data_cost = shots * _safe_log(support)

    # Structured data cost is the ideal Shannon code.  Complexity pays for the
    # free simplex coordinates plus the explicitly searched projection family.
    entropy = float(record.entropy)
    structured_data_cost = shots * entropy
    simplex_cost = 0.5 * max(support - 1, 0) * _safe_log(shots + 1.0)
    candidate_count = max(len(record.projection_scores), 1)
    selection_cost = _safe_log(candidate_count)
    model_cost = simplex_cost + selection_cost
    structured_total = structured_data_cost + model_cost
    gain = null_data_cost - structured_total
    gap = minimum_gain - gain

    return MDLEvidenceLedger(
        carrier=v2.CarrierType.QUTRIT.value,
        null_model=f"uniform_categorical_{support}",
        structured_model=f"selected_{record.observable_family}_simplex",
        null_code_length=float(null_data_cost),
        structured_code_length=float(structured_total),
        model_code_length=float(model_cost),
        selection_code_length=float(selection_cost),
        evidence_gain=float(gain),
        minimum_gain=float(minimum_gain),
        promotability_gap=float(gap),
        sufficient=bool(gap <= 0.0 and record.selected_projection_score > 0.0),
        terms={
            "support": float(support),
            "shots": float(shots),
            "entropy": entropy,
            "entropy_gap": float(record.entropy_gap),
            "simplex_cost": simplex_cost,
            "projection_candidates": float(candidate_count),
            "selected_projection_score": float(record.selected_projection_score),
        },
        assumptions=(
            "the measured qutrit/motif distribution is coded categorically",
            "projection search pays log(number of candidate projections)",
            "the simplex pays a BIC-style half-log-n cost per free coordinate",
            "latent qutrit amplitudes remain non-canonical",
        ),
    )


def _triality_ledger(
    record: v2.TrialityMeasurementRecord,
    minimum_gain: float,
) -> MDLEvidenceLedger:
    shots = max(int(record.shots), 1)
    sigma = _normal_sigma(record.variance, shots)
    correlation = abs(float(record.correlation))
    z = correlation / sigma
    null_data_cost = 0.5 * z * z

    pair_key = f"{record.selected_pair[0]}{record.selected_pair[1]}"
    selected_terms = record.pair_scores.get(pair_key, {})
    intrinsic_mdl = float(selected_terms.get("mdl_cost", 0.0))
    pair_count = max(len(record.pair_scores), 1)
    selection_cost = _safe_log(pair_count)
    parameter_cost = 0.5 * _safe_log(shots + 1.0)
    model_cost = intrinsic_mdl + selection_cost + parameter_cost
    structured_data_cost = 0.0
    structured_total = structured_data_cost + model_cost
    gain = null_data_cost - structured_total
    gap = minimum_gain - gain

    return MDLEvidenceLedger(
        carrier=v2.CarrierType.TRIALITY.value,
        null_model="zero_pair_correlation",
        structured_model="selected_triality_pair_correlation",
        null_code_length=float(null_data_cost),
        structured_code_length=float(structured_total),
        model_code_length=float(model_cost),
        selection_code_length=float(selection_cost),
        evidence_gain=float(gain),
        minimum_gain=float(minimum_gain),
        promotability_gap=float(gap),
        sufficient=bool(gap <= 0.0 and record.selected_pair_score > 0.0),
        terms={
            "correlation_abs": correlation,
            "standard_error": sigma,
            "z_correlation": z,
            "selected_pair_score": float(record.selected_pair_score),
            "intrinsic_pair_mdl_cost": intrinsic_mdl,
            "pair_candidates": float(pair_count),
            "parameter_cost": parameter_cost,
        },
        assumptions=(
            "selected-pair correlation is summarized by an approximately normal error scale",
            "pair selection pays log(number of candidate pairs)",
            "the v2 intrinsic signal/stability/symmetry MDL cost is retained",
            "selection, measurement, and promotion remain distinct steps",
        ),
    )


def mdl_evidence_ledger(
    record: Any,
    carrier_type: v2.CarrierType,
    minimum_gain: float = 0.0,
) -> MDLEvidenceLedger:
    if carrier_type == v2.CarrierType.QUBIT:
        return _qubit_ledger(record, minimum_gain)
    if carrier_type == v2.CarrierType.QUTRIT:
        return _qutrit_ledger(record, minimum_gain)
    if carrier_type == v2.CarrierType.TRIALITY:
        return _triality_ledger(record, minimum_gain)
    raise ValueError(f"unsupported carrier type: {carrier_type}")


def govern_candidate_promotion(
    candidate: v2.PromotionResult,
    ledger: MDLEvidenceLedger,
) -> GovernedPromotionResult:
    accepted = bool(candidate.accepted and ledger.sufficient)
    if not candidate.accepted:
        reason = f"candidate_rejected:{candidate.reason}"
    elif not ledger.sufficient:
        reason = "mdl_evidence_insufficient"
    else:
        reason = "candidate_and_mdl_evidence_sufficient"

    return GovernedPromotionResult(
        accepted=accepted,
        reason=reason,
        candidate_promotion=candidate,
        mdl_evidence=ledger,
        datum=dict(candidate.datum),
    )


def run_governed_pipeline(
    job: v2.PipelineJob,
    shots: int = 200,
    minimum_gain: float = 0.0,
) -> dict[str, Any]:
    base = v2.run_typed_pipeline(job, shots=shots)
    ledger = mdl_evidence_ledger(
        base["record"],
        job.carrier.carrier_type,
        minimum_gain=minimum_gain,
    )
    governed = govern_candidate_promotion(base["promotion"], ledger)

    witness = dict(base["witness"])
    witness["witness_schema"] = "dashiQ.quantum_bridge.v3"
    witness["candidate_promotion"] = witness.get("promotion")
    witness["mdl_evidence"] = asdict(ledger)
    witness["promotion"] = {
        "accepted": governed.accepted,
        "reason": governed.reason,
        "requires_candidate_acceptance": True,
        "requires_mdl_sufficiency": True,
    }
    witness["claim_status"] = (
        "promoted_classical_evidence"
        if governed.accepted
        else "candidate_or_blocked_classical_evidence"
    )

    return {
        **base,
        "heuristic_gap_v2": base["gap"],
        "gap": ledger.promotability_gap,
        "mdl_evidence": ledger,
        "promotion": governed,
        "witness": witness,
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def run_computer_v3(
    shots: int = 200,
    minimum_gain: float = 0.0,
) -> dict[str, dict[str, Any]]:
    jobs = {
        "qubit_lattice": v2.prepare_qubit_lattice_job(),
        "qutrit_planes": v2.prepare_qutrit_planes_job(),
        "qutrit_motif27": v2.prepare_qutrit_motif27_job(),
        "triality_frames": v2.prepare_triality_job(),
    }
    return {
        name: run_governed_pipeline(
            job,
            shots=shots,
            minimum_gain=minimum_gain,
        )
        for name, job in jobs.items()
    }


def write_v3_artifact(
    path: str | Path = "gpt_experiments/computer_v3_mdl_governance.json",
    shots: int = 200,
    minimum_gain: float = 0.0,
) -> Path:
    outputs = run_computer_v3(shots=shots, minimum_gain=minimum_gain)
    artifact = {
        "schema": "dashiQ.computer_v3.mdl_governance.v1",
        "shots": shots,
        "minimum_gain": minimum_gain,
        "systems": {
            name: {
                "promotion": _jsonable(output["promotion"]),
                "mdl_evidence": _jsonable(output["mdl_evidence"]),
                "heuristic_gap_v2": output["heuristic_gap_v2"],
                "witness": _jsonable(output["witness"]),
            }
            for name, output in outputs.items()
        },
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, indent=2, sort_keys=True))
    return target


def main() -> None:
    outputs = run_computer_v3()
    for name, output in outputs.items():
        ledger = output["mdl_evidence"]
        promotion = output["promotion"]
        print(f"\n=== {name} ===")
        print(f"candidate accepted: {promotion.candidate_promotion.accepted}")
        print(f"MDL evidence gain: {ledger.evidence_gain:.6f}")
        print(f"promotability gap: {ledger.promotability_gap:.6f}")
        print(f"DASHI promotion: {promotion.accepted} ({promotion.reason})")


if __name__ == "__main__":
    main()
