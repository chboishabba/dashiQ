"""Shared QG motif candidate models for dashiQ.

This module keeps the qutrit motif source families explicit and comparable.
Each model returns:

- `weights27`: a 27-state probability vector
- `metadata`: provenance and internal model details

The runtime in `computer_v2.py` remains the measurement/promotion layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

import computer_v1 as _v1


@dataclass(frozen=True)
class ModelOutput:
    weights27: np.ndarray
    metadata: dict[str, Any]


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


def _triplet_index(i: int, j: int, k: int) -> int:
    return 9 * i + 3 * j + k


def _normalize_weights(weights: np.ndarray) -> np.ndarray:
    out = np.asarray(weights, dtype=float).copy()
    total = float(np.sum(out))
    if total <= 0.0:
        raise ValueError("weights must sum to a positive value")
    out /= total
    return out


def _coarse9_from_weights27(weights27: np.ndarray) -> np.ndarray:
    if _v1._dashifine_map_27_to_H3x3 is None:
        raise RuntimeError("qg motif models require dashifine map_27_to_H3x3")
    return _v1._dashifine_map_27_to_H3x3.coarse9_from_weights27(weights27)


def _permute_basis9(base: np.ndarray, shift_a: int = 0, shift_b: int = 0, swap: bool = False) -> np.ndarray:
    mapping: list[int] = []
    for a in range(3):
        for b in range(3):
            aa, bb = (b, a) if swap else (a, b)
            aa = (aa + shift_a) % 3
            bb = (bb + shift_b) % 3
            mapping.append(aa * 3 + bb)
    return base[mapping]


def _projection_candidates_motif9(probabilities: np.ndarray) -> dict[str, np.ndarray]:
    base = np.asarray(probabilities, dtype=float)
    return {
        "motif_identity": base,
        "motif_roll_1": np.roll(base, 1),
        "motif_roll_2": np.roll(base, 2),
        "motif_roll_3": np.roll(base, 3),
    }


def _score_projection(probabilities: np.ndarray) -> tuple[float, dict[str, float]]:
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


def summarize_model(weights27: np.ndarray) -> dict[str, Any]:
    coarse9 = _coarse9_from_weights27(weights27)
    candidates = _projection_candidates_motif9(coarse9)
    scored = {}
    for name, probs in candidates.items():
        _, metrics = _score_projection(probs)
        scored[name] = metrics
    selected = max(scored, key=lambda name: scored[name]["score"])
    return {
        "latent_support_27": int(np.count_nonzero(weights27 > 1e-12)),
        "coarse_support_9": int(np.count_nonzero(coarse9 > 1e-12)),
        "coarse_entropy": _shannon_entropy(coarse9),
        "selected_projection": selected,
        "selected_projection_score": float(scored[selected]["score"]),
        "entropy_gap": float(scored[selected]["entropy_gap"]),
        "projection_scores": scored,
    }


def motif_weights27_qg(
    beta_model: float = 2.5,
    beta_resid: float = 1.15,
    beta_pattern: float = 0.60,
) -> ModelOutput:
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
                weights[_triplet_index(i, j, k)] = float(np.exp(-mdl_cost))
    weights = _normalize_weights(weights)
    coarse9 = _coarse9_from_weights27(weights)
    return ModelOutput(
        weights,
        {
            "agda_source": (
                "DASHI.Physics.LiftToFullState.coarseProj + "
                "DASHI.Physics.Closure.MDLTradeoffShiftInstance.MDLPartsShift"
            ),
            "model_kind": "qg_mdl",
            "coarse_tail_split": {"m": 2, "k": 1},
            "beta_model": beta_model,
            "beta_resid": beta_resid,
            "beta_pattern": beta_pattern,
            "model_len": "countNZ(coarse)",
            "resid_len": "countNZ(tail)",
            "pattern_len": "coarse disagreement / code penalty",
            "coarse_observable_eliminates_tail_scale": True,
            "coarse_entropy": _shannon_entropy(coarse9),
        },
    )


def _cyclic_triplet_views(i: int, j: int, k: int) -> tuple[tuple[int, int, int], ...]:
    return ((i, j, k), (j, k, i), (k, i, j))


def motif_weights27_qg_dynamics(
    beta_model: float = 2.5,
    beta_resid: float = 1.15,
    beta_pattern: float = 0.60,
    beta_cycle: float = 0.85,
) -> ModelOutput:
    static = motif_weights27_qg(beta_model=beta_model, beta_resid=beta_resid, beta_pattern=beta_pattern)
    weights = np.zeros(27, dtype=float)
    for i in range(3):
        for j in range(3):
            for k in range(3):
                idx = _triplet_index(i, j, k)
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
                weights[idx] = static.weights27[idx] * cycle_score
    weights = _normalize_weights(weights)
    coarse9 = _coarse9_from_weights27(weights)
    return ModelOutput(
        weights,
        {
            "agda_source": (
                "DASHI.Physics.TailCollapseProof.Tᵣ/iterate + "
                "DASHI.Physics.LiftToFullState.coarseProj + "
                "DASHI.Physics.Closure.MDLTradeoffShiftInstance.MDLPartsShift"
            ),
            "model_kind": "qg_dynamics",
            "dynamics_model": "cyclic_coarse_tail_ensemble",
            "coarse_tail_split": {"m": 2, "k": 1},
            "beta_model": beta_model,
            "beta_resid": beta_resid,
            "beta_pattern": beta_pattern,
            "beta_cycle": beta_cycle,
            "cyclic_views": ["(i,j)|k", "(j,k)|i", "(k,i)|j"],
            "reference_prior": static.metadata,
            "coarse_entropy": _shannon_entropy(coarse9),
        },
    )


def _tail_step2(c: int, d: int) -> tuple[int, int]:
    return d, 0


def _resid_count_to_trit(count: int) -> int:
    return int(max(0, min(2, count)))


def motif_weights27_qg_large_tail(
    beta_model: float = 2.1,
    beta_resid: float = 1.0,
    beta_pattern: float = 0.50,
) -> ModelOutput:
    weights27 = np.zeros(27, dtype=float)
    for a in range(3):
        for b in range(3):
            for c in range(3):
                for d in range(3):
                    model_len = _trit_nz(a) + _trit_nz(b)
                    resid_len = _trit_nz(c) + _trit_nz(d)
                    pattern_len = _coarse_pattern_penalty(a, b)
                    state_weight = float(
                        np.exp(-(beta_model * model_len + beta_resid * resid_len + beta_pattern * pattern_len))
                    )
                    tail = (c, d)
                    for _ in range(3):
                        resid_trit = _resid_count_to_trit(_trit_nz(tail[0]) + _trit_nz(tail[1]))
                        weights27[_triplet_index(a, b, resid_trit)] += state_weight / 3.0
                        tail = _tail_step2(*tail)
    weights27 = _normalize_weights(weights27)
    return ModelOutput(
        weights27,
        {
            "agda_source": "DASHI.Physics.TailCollapseProof.Tᵣ/iterate",
            "model_kind": "qg_large_tail",
            "coarse_tail_split": {"m": 2, "k": 2},
            "latent_dimension": 81,
            "trajectory_average_steps": [0, 1, 2],
        },
    )


def motif_weights27_qg_ensemble(
    beta_model: float = 2.1,
    beta_resid: float = 1.0,
    beta_pattern: float = 0.50,
    beta_collapse: float = 0.70,
) -> ModelOutput:
    weights27 = np.zeros(27, dtype=float)
    for a in range(3):
        for b in range(3):
            for c in range(3):
                for d in range(3):
                    model_len = _trit_nz(a) + _trit_nz(b)
                    pattern_len = _coarse_pattern_penalty(a, b)
                    tail = (c, d)
                    for step in range(3):
                        resid_len = _trit_nz(tail[0]) + _trit_nz(tail[1])
                        traj_weight = float(
                            np.exp(
                                -(
                                    beta_model * model_len
                                    + beta_pattern * pattern_len
                                    + beta_resid * resid_len
                                    + beta_collapse * step
                                )
                            )
                        )
                        resid_trit = _resid_count_to_trit(resid_len)
                        weights27[_triplet_index(a, b, resid_trit)] += traj_weight
                        tail = _tail_step2(*tail)
    weights27 = _normalize_weights(weights27)
    return ModelOutput(
        weights27,
        {
            "agda_source": "DASHI.Physics.TailCollapseProof.iterate + MDLPartsShift",
            "model_kind": "qg_ensemble",
            "coarse_tail_split": {"m": 2, "k": 2},
            "latent_dimension": 81,
            "ensemble_mode": "deterministic_enumeration",
            "beta_collapse": beta_collapse,
        },
    )


def motif_weights27_qg_projection_covariant(
    beta_model: float = 2.0,
    beta_orbit: float = 0.75,
) -> ModelOutput:
    orbit_weights: dict[tuple[int, int, int, int, int], float] = {}
    for a in range(3):
        for b in range(3):
            for c in range(3):
                for d in range(3):
                    r0 = _resid_count_to_trit(_trit_nz(c) + _trit_nz(d))
                    d1, _ = _tail_step2(c, d)
                    r1 = _resid_count_to_trit(_trit_nz(d1))
                    r2 = 0
                    orbit = (a, b, r0, r1, r2)
                    model_len = _trit_nz(a) + _trit_nz(b)
                    orbit_cost = beta_model * model_len + beta_orbit * (r0 + r1 + r2)
                    orbit_weights.setdefault(orbit, float(np.exp(-orbit_cost)))

    weights27 = np.zeros(27, dtype=float)
    for (a, b, r0, r1, r2), weight in orbit_weights.items():
        for resid in (r0, r1, r2):
            weights27[_triplet_index(a, b, resid)] += weight / 3.0
    weights27 = _normalize_weights(weights27)
    return ModelOutput(
        weights27,
        {
            "agda_source": "DASHI.Physics.LiftToFullState.coarse-invariant-T + MDLPartsShift",
            "model_kind": "qg_projection_covariant",
            "orbit_basis": "coarse image + residual profile",
            "coarse_tail_split": {"m": 2, "k": 2},
            "beta_model": beta_model,
            "beta_orbit": beta_orbit,
        },
    )


def motif_weights27_qg_large_tail_v2(
    beta_model: float = 2.0,
    beta_resid: float = 1.0,
    beta_pattern: float = 0.50,
    step_decay: float = 0.6,
) -> ModelOutput:
    """Larger latent carrier with trajectory-weighted coarse accumulation (m=2,k=2)."""
    weights27 = np.zeros(27, dtype=float)
    for a in range(3):
        for b in range(3):
            for c in range(3):
                for d in range(3):
                    model_len = _trit_nz(a) + _trit_nz(b)
                    pattern_len = _coarse_pattern_penalty(a, b)
                    tail = (c, d)
                    decay = 1.0
                    for step in range(4):
                        resid_len = _trit_nz(tail[0]) + _trit_nz(tail[1])
                        cost = (
                            beta_model * model_len
                            + beta_resid * resid_len
                            + beta_pattern * pattern_len
                        )
                        weight = float(np.exp(-cost) * decay)
                        resid_trit = _resid_count_to_trit(resid_len)
                        weights27[_triplet_index(a, b, resid_trit)] += weight
                        decay *= step_decay
                        tail = _tail_step2(*tail)
    weights27 = _normalize_weights(weights27)
    return ModelOutput(
        weights27,
        {
            "agda_source": "DASHI.Physics.TailCollapseProof.Tᵣ trajectory average (m=2,k=2)",
            "model_kind": "qg_large_tail_v2",
            "coarse_tail_split": {"m": 2, "k": 2},
            "latent_dimension": 81,
            "step_decay": step_decay,
        },
    )


def motif_weights27_qg_triality_coupled(
    triality_context: dict[str, Any],
    beta_model: float = 2.0,
) -> ModelOutput:
    selected_pair = tuple(triality_context.get("selected_pair", [0, 1]))
    pair_bias = float(triality_context.get("pair_bias", 0.75))
    mdl_cost = float(triality_context.get("mdl_cost", 0.25))
    weights27 = np.zeros(27, dtype=float)
    favored = {selected_pair[0], selected_pair[1]}
    for a in range(3):
        for b in range(3):
            pair_match = 1.0 if a in favored and b in favored else 0.35
            for k in range(3):
                model_len = _trit_nz(a) + _trit_nz(b)
                resid_len = _trit_nz(k)
                cost = beta_model * model_len + mdl_cost * resid_len
                weights27[_triplet_index(a, b, k)] = float(np.exp(-cost) * (pair_bias * pair_match))
    weights27 = _normalize_weights(weights27)
    return ModelOutput(
        weights27,
        {
            "model_kind": "qg_triality_coupled",
            "coupling_source": triality_context,
            "mapping": "selected_pair -> favored coarse sectors; triality mdl_cost -> residual penalty",
        },
    )


def motif_weights27_qg_ccr_experimental(
    beta_model: float = 2.5,
    beta_resid: float = 1.15,
    beta_pattern: float = 0.60,
    mix: float = 0.30,
) -> ModelOutput:
    static = motif_weights27_qg(beta_model=beta_model, beta_resid=beta_resid, beta_pattern=beta_pattern)
    base = static.weights27.reshape(3, 3, 3)
    translated = np.roll(base, shift=1, axis=2)
    mixed = _normalize_weights(((1.0 - mix) * base + mix * translated).reshape(27))
    return ModelOutput(
        mixed,
        {
            "agda_source": "DASHI.Algebra.Quantum.CCRFromProjection (experimental inspiration only)",
            "model_kind": "qg_ccr_experimental",
            "operator_family": "residual_translation_mix",
            "mix": mix,
            "reference_prior": static.metadata,
            "experimental": True,
        },
    )


def build_model(
    model: str,
    config: dict[str, Any] | None = None,
) -> ModelOutput:
    cfg = dict(config or {})
    if model == "qg_mdl":
        return motif_weights27_qg(**{k: cfg[k] for k in ("beta_model", "beta_resid", "beta_pattern") if k in cfg})
    if model == "qg_dynamics":
        return motif_weights27_qg_dynamics(
            **{k: cfg[k] for k in ("beta_model", "beta_resid", "beta_pattern", "beta_cycle") if k in cfg}
        )
    if model == "qg_large_tail":
        return motif_weights27_qg_large_tail(
            **{k: cfg[k] for k in ("beta_model", "beta_resid", "beta_pattern") if k in cfg}
        )
    if model == "qg_ensemble":
        return motif_weights27_qg_ensemble(
            **{k: cfg[k] for k in ("beta_model", "beta_resid", "beta_pattern", "beta_collapse") if k in cfg}
        )
    if model == "qg_projection_covariant":
        return motif_weights27_qg_projection_covariant(
            **{k: cfg[k] for k in ("beta_model", "beta_orbit") if k in cfg}
        )
    if model == "qg_large_tail_v2":
        return motif_weights27_qg_large_tail_v2(
            **{
                k: cfg[k]
                for k in ("beta_model", "beta_resid", "beta_pattern", "step_decay")
                if k in cfg
            }
        )
    if model == "qg_triality_coupled":
        return motif_weights27_qg_triality_coupled(cfg["triality_context"], beta_model=float(cfg.get("beta_model", 2.0)))
    if model == "qg_ccr_experimental":
        return motif_weights27_qg_ccr_experimental(
            **{k: cfg[k] for k in ("beta_model", "beta_resid", "beta_pattern", "mix") if k in cfg}
        )
    raise ValueError(f"unknown qg motif model: {model}")


def build_comparison(
    selected_model: str,
    compare_models: list[str],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_names = [selected_model] + [name for name in compare_models if name != selected_model]
    outputs: dict[str, Any] = {}
    for name in model_names:
        model_out = build_model(name, config=config)
        outputs[name] = {
            "summary": summarize_model(model_out.weights27),
            "metadata": model_out.metadata,
        }
    baseline = outputs[selected_model]
    baseline_summary = baseline["summary"]
    ranking = sorted(
        (
            {
                "model": name,
                "selected_projection_score": float(payload["summary"]["selected_projection_score"]),
                "entropy_gap": float(payload["summary"]["entropy_gap"]),
                "coarse_entropy": float(payload["summary"]["coarse_entropy"]),
                "experimental": bool(payload["metadata"].get("experimental", False)),
            }
            for name, payload in outputs.items()
        ),
        key=lambda row: (row["selected_projection_score"], row["entropy_gap"]),
        reverse=True,
    )
    winners = []
    for row in ranking:
        if row["model"] == selected_model:
            continue
        if row["experimental"]:
            continue
        if (
            row["selected_projection_score"] > float(baseline_summary["selected_projection_score"])
            and row["entropy_gap"] > float(baseline_summary["entropy_gap"])
        ):
            winners.append(row["model"])
    return {
        "selected_model": selected_model,
        "comparison_models": model_names,
        "model_outputs": outputs,
        "ranking": ranking,
        "replacement_policy": {
            "name": "beat_baseline_on_score_and_gap_nonexperimental",
            "baseline_model": selected_model,
            "baseline_summary": {
                "selected_projection_score": float(baseline_summary["selected_projection_score"]),
                "entropy_gap": float(baseline_summary["entropy_gap"]),
                "coarse_entropy": float(baseline_summary["coarse_entropy"]),
            },
            "qualifying_models": winners,
            "decision": winners[0] if winners else selected_model,
            "retain_baseline": len(winners) == 0,
        },
    }
