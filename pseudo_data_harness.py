"""
Pseudo-data harness for MDL structure detectability.

This script generates pseudo-data from a reference shape plus controlled
injections, using real published covariance, and measures MDL selection rates.
It does not modify the core analysis code; it is a standalone validation tool.
"""

import argparse
import math
import multiprocessing as mp
import requests
import numpy as np
from scipy.optimize import minimize


# ----------------------------
# CONFIG
# ----------------------------
HEPDATA_RECORD = "137886"  # ATLAS 13 TeV H→γγ differential XS
OBSERVABLES = [
    ("pT_yy", "pT_yy_corr", "log"),
    ("yAbs_yy", "yAbs_yy_corr", "linear"),
    ("N_j_30", "N_j_30_corr", "ordinal"),
]

MDL_LAMBDA = 1.0


# ----------------------------
# HEPData helpers
# ----------------------------
def _get_json(url, context="resource"):
    resp = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_table(record, table_name):
    url = f"https://www.hepdata.net/record/{record}?format=json"
    data = _get_json(url, context="record")
    tables = data.get("tables") or data.get("data_tables") or []
    for table in tables:
        name = table.get("title") or table.get("name")
        if name == table_name:
            data_block = table.get("data", {})
            if isinstance(data_block, dict) and "json" in data_block:
                return _get_json(data_block["json"], context="table")
            if "location" in table:
                table_url = "https://www.hepdata.net" + table["location"]
                return _get_json(table_url + "?format=json", context="table")
            break
    raise RuntimeError(f"Table {table_name!r} not found for record {record}")


def _parse_bin_center(x_entry):
    if "low" in x_entry and "high" in x_entry:
        return 0.5 * (float(x_entry["low"]) + float(x_entry["high"]))
    if "value" in x_entry:
        val = str(x_entry["value"]).strip()
        if val.startswith("="):
            return float(val[1:])
        if "\\geq" in val or "≥" in val or val.startswith(">="):
            val = (
                val.replace("$", "")
                .replace("\\geq", ">=")
                .replace("≥", ">=")
                .replace(" ", "")
            )
            return float(val.replace(">=", ""))
        if "-" in val:
            parts = [p.strip() for p in val.split("-")]
            if len(parts) == 2:
                return 0.5 * (float(parts[0]) + float(parts[1]))
        return float(val)
    raise RuntimeError(f"Unrecognized bin format: {x_entry}")


def _parse_bin_edges(value):
    if isinstance(value, (int, float)):
        val = float(value)
        return val, val
    text = str(value).replace("GeV", "").strip()
    if text.startswith("="):
        val = float(text[1:])
        return val, val
    if "\\geq" in text or "≥" in text or text.startswith(">="):
        text = (
            text.replace("$", "")
            .replace("\\geq", ">=")
            .replace("≥", ">=")
            .replace(" ", "")
        )
        val = float(text.replace(">=", ""))
        return val, val
    if text.startswith("(") and ")" in text:
        text = text.strip("()")
        parts = [p.strip() for p in text.split(",")]
        if len(parts) == 2:
            return float(parts[0]), float(parts[1])
    if "-" in text:
        parts = [p.strip() for p in text.split("-")]
        if len(parts) == 2:
            return float(parts[0]), float(parts[1])
    raise RuntimeError(f"Unrecognized bin edge format: {value}")


def _combine_errors(errors):
    if not errors:
        return 0.0
    var = 0.0
    for err in errors:
        if "asymerror" in err:
            minus = float(err["asymerror"]["minus"])
            plus = float(err["asymerror"]["plus"])
            sym = 0.5 * (abs(minus) + abs(plus))
        else:
            sym = float(err.get("symerror", 0.0))
        var += sym * sym
    return np.sqrt(var)


def extract_binned_values(table):
    ys_data = []
    sigmas = []
    bin_edges = []
    bin_centers = []
    is_categorical = False

    for row in table["values"]:
        x_entry = row["x"][0]
        bin_centers.append(_parse_bin_center(x_entry))
        if "low" in x_entry and "high" in x_entry:
            bin_edges.append((float(x_entry["low"]), float(x_entry["high"])))
        else:
            is_categorical = True
            bin_edges.append(_parse_bin_edges(x_entry.get("value")))
        cell = row["y"][0]
        ys_data.append(float(cell["value"]))
        sigmas.append(_combine_errors(cell.get("errors", [])))

    return (
        np.array(bin_centers),
        np.array(ys_data),
        np.array(sigmas),
        bin_edges,
        is_categorical,
    )


def extract_correlation_matrix(table, bin_edges):
    n = len(bin_edges)
    corr = np.eye(n)
    index = {edge: i for i, edge in enumerate(bin_edges)}
    for row in table["values"]:
        x0 = _parse_bin_edges(row["x"][0]["value"])
        x1 = _parse_bin_edges(row["x"][1]["value"])
        i = index[x0]
        j = index[x1]
        corr[i, j] = float(row["y"][0]["value"])
    return corr


# ----------------------------
# Models
# ----------------------------
def _basis(x, basis):
    x0 = np.mean(x)
    if basis == "log":
        return np.log(x / x0)
    if basis in ("linear", "ordinal"):
        return x - x0
    raise ValueError(f"Unknown basis: {basis}")


def model_A(params, x, y_ref, basis):
    log_a = params[0]
    return np.exp(log_a) * y_ref


def model_B(params, x, y_ref, basis):
    log_a, b = params
    u = _basis(x, basis)
    return np.exp(log_a + b * u) * y_ref


def model_C(params, x, y_ref, basis):
    log_a, b, c = params
    u = _basis(x, basis)
    return np.exp(log_a + b * u + c * u ** 2) * y_ref


def chi2(params, model, x, y, y_ref, cov_inv, basis):
    diff = y - model(params, x, y_ref, basis)
    return diff.T @ cov_inv @ diff


def fit_model(model, n_params, x, y, y_ref, cov_inv, basis):
    init = np.zeros(n_params)
    mean_y = max(float(np.mean(y)), 1e-12)
    init[0] = np.log(mean_y)
    res = minimize(
        chi2,
        init,
        args=(model, x, y, y_ref, cov_inv, basis),
        method="Nelder-Mead",
    )
    return res.fun, res.x


def mdl_score(chi2_val, k, n):
    return chi2_val + MDL_LAMBDA * k * math.log(n)


# ----------------------------
# Pseudo-data generation
# ----------------------------
def spectral_discreteness(
    y,
    peak_prominence=5.0,
    peak_width=1,
    baseline_mode="global",
    baseline_window=5,
    debug=False,
):
    y = np.asarray(y, dtype=float)
    if y.size < 3:
        return (0.0, 0, {}) if debug else (0.0, 0)
    y_shift = y - float(np.min(y))
    if baseline_mode == "local":
        window = max(int(baseline_window), 1)
        if window > len(y_shift):
            window = len(y_shift)
        if window > 1:
            kernel = np.ones(window, dtype=float) / float(window)
            baseline = np.convolve(y_shift, kernel, mode="same")
            y_shift = y_shift - baseline
            y_shift = np.clip(y_shift, 0.0, None)
    total = float(np.sum(y_shift))
    if total <= 0:
        return (0.0, 0, {}) if debug else (0.0, 0)
    positive = y_shift[y_shift > 0]
    median = float(np.median(positive)) if positive.size else 0.0
    if median <= 0:
        median = total / max(len(y_shift), 1)
    max_val = float(np.max(y_shift))
    if max_val > 0 and median >= 0.9 * max_val:
        threshold = 0.5 * max_val
    else:
        threshold = peak_prominence * median
    used = np.zeros_like(y_shift, dtype=bool)
    peak_power = 0.0
    peaks = 0
    for i in range(len(y_shift)):
        if used[i]:
            continue
        left = y_shift[i - 1] if i > 0 else -np.inf
        right = y_shift[i + 1] if i < len(y_shift) - 1 else -np.inf
        if y_shift[i] > left and y_shift[i] > right and y_shift[i] >= threshold:
            lo = max(i - peak_width, 0)
            hi = min(i + peak_width + 1, len(y_shift))
            peak_power += float(np.sum(y_shift[lo:hi]))
            used[lo:hi] = True
            peaks += 1
    result = min(peak_power / total, 1.0), peaks
    if debug:
        info = {
            "max": max_val,
            "median": float(median),
            "threshold": float(threshold),
            "total": float(total),
        }
        return result[0], result[1], info
    return result


def make_reference_shape(x, kind):
    if kind == "flat":
        return np.ones_like(x)
    if kind == "powerlaw_exp":
        x0 = np.mean(x)
        return (x / x0) ** -1.5 * np.exp(-0.02 * x)
    if kind == "gaussian_lines":
        centers = np.linspace(np.min(x), np.max(x), 3)
        if len(x) > 1:
            sorted_x = np.sort(x)
            dx = float(np.median(np.diff(sorted_x)))
            widths = np.full_like(centers, max(0.5 * dx, 1e-9))
        else:
            widths = np.full_like(centers, 1.0)
        y = np.zeros_like(x, dtype=float)
        for c, w in zip(centers, widths):
            y += np.exp(-0.5 * ((x - c) / w) ** 2)
        return y / np.max(y)
    raise ValueError(f"Unknown reference kind: {kind}")


def inject_deformation(x, y_ref, basis, kind, epsilon, dim_b=1.0, dim_c=0.0):
    if kind == "none":
        return y_ref
    u = _basis(x, basis)
    if kind == "tilt":
        return y_ref * np.exp(epsilon * u)
    if kind == "curvature":
        return y_ref * np.exp(epsilon * (u ** 2))
    if kind == "lines":
        lines = make_reference_shape(x, "gaussian_lines")
        return y_ref * np.exp(epsilon * lines)
    if kind == "dimension":
        return y_ref * np.exp(epsilon * (dim_b * u + dim_c * (u ** 2)))
    raise ValueError(f"Unknown injection kind: {kind}")


def cumulative_projection_matrix(bin_edges, n_bins):
    if bin_edges is None or len(bin_edges) != n_bins + 1:
        widths = np.ones(n_bins, dtype=float)
    else:
        widths = np.diff(bin_edges)
    proj = np.zeros((n_bins, n_bins), dtype=float)
    for i in range(n_bins):
        proj[i, i:] = widths[i:]
    return proj


def sample_pseudo(y_true, cov, rng):
    L = np.linalg.cholesky(cov)
    z = rng.standard_normal(len(y_true))
    return y_true + L @ z


# ----------------------------
# Harness
# ----------------------------
def run_observable(
    table_name,
    corr_table_name,
    basis,
    ref_kind,
    inject,
    epsilon,
    n_trials,
    rng,
    spectral_cfg=None,
    dim_b=1.0,
    dim_c=0.0,
    projection="raw",
):
    xs_table = fetch_table(HEPDATA_RECORD, table_name)
    corr_table = fetch_table(HEPDATA_RECORD, corr_table_name)

    x, y_data, sigma, bin_edges, is_categorical = extract_binned_values(xs_table)
    if basis == "ordinal" or is_categorical:
        x = np.arange(1, len(x) + 1, dtype=float)
    elif basis == "log" and np.any(x <= 0):
        raise RuntimeError(
            f"{table_name} has non-positive x for log basis; use linear/ordinal."
        )

    corr = extract_correlation_matrix(corr_table, bin_edges)
    cov = np.outer(sigma, sigma) * corr

    y_ref = make_reference_shape(x, ref_kind)
    y_true = inject_deformation(x, y_ref, basis, inject, epsilon, dim_b=dim_b, dim_c=dim_c)

    if projection == "cumulative":
        proj = cumulative_projection_matrix(bin_edges, len(y_true))
        y_ref = proj @ y_ref
        y_true = proj @ y_true
        cov = proj @ cov @ proj.T

    cov_inv = np.linalg.inv(cov)

    counts = {"A": 0, "B": 0, "C": 0}
    spectral = None
    if spectral_cfg:
        if spectral_cfg.get("debug"):
            d_true, peaks_true, dbg = spectral_discreteness(
                y_true,
                peak_prominence=spectral_cfg["peak_prominence"],
                peak_width=spectral_cfg["peak_width"],
                baseline_mode=spectral_cfg["baseline_mode"],
                baseline_window=spectral_cfg["baseline_window"],
                debug=True,
            )
            spectral = {"true": (d_true, peaks_true), "samples": [], "debug": dbg}
        else:
            d_true, peaks_true = spectral_discreteness(
                y_true,
                peak_prominence=spectral_cfg["peak_prominence"],
                peak_width=spectral_cfg["peak_width"],
                baseline_mode=spectral_cfg["baseline_mode"],
                baseline_window=spectral_cfg["baseline_window"],
            )
            spectral = {"true": (d_true, peaks_true), "samples": []}
    for _ in range(n_trials):
        y = sample_pseudo(y_true, cov, rng)
        chi2_A, _ = fit_model(model_A, 1, x, y, y_ref, cov_inv, basis)
        chi2_B, _ = fit_model(model_B, 2, x, y, y_ref, cov_inv, basis)
        chi2_C, _ = fit_model(model_C, 3, x, y, y_ref, cov_inv, basis)

        mdl_A = mdl_score(chi2_A, 1, len(y))
        mdl_B = mdl_score(chi2_B, 2, len(y))
        mdl_C = mdl_score(chi2_C, 3, len(y))
        best = min([("A", mdl_A), ("B", mdl_B), ("C", mdl_C)], key=lambda v: v[1])[0]
        counts[best] += 1
        if spectral is not None:
            d_sample, peaks_sample = spectral_discreteness(
                y,
                peak_prominence=spectral_cfg["peak_prominence"],
                peak_width=spectral_cfg["peak_width"],
                baseline_mode=spectral_cfg["baseline_mode"],
                baseline_window=spectral_cfg["baseline_window"],
            )
            spectral["samples"].append((d_sample, peaks_sample))

    return counts, spectral


def detection_rate(counts, inject, dim_c=0.0):
    total = sum(counts.values())
    if total == 0:
        return 0.0
    if inject == "tilt":
        return counts["B"] / total
    if inject == "curvature":
        return counts["C"] / total
    if inject == "lines":
        return (counts["B"] + counts["C"]) / total
    if inject == "dimension":
        return (counts["C"] if dim_c != 0.0 else counts["B"]) / total
    return 0.0


def scan_epsilons(
    epsilons,
    table_name,
    corr_table_name,
    basis,
    ref_kind,
    inject,
    n_trials,
    rng,
    dim_b=1.0,
    dim_c=0.0,
    projection="raw",
):
    rows = []
    for eps in epsilons:
        counts, _ = run_observable(
            table_name,
            corr_table_name,
            basis,
            ref_kind,
            inject,
            eps,
            n_trials,
            rng,
            dim_b=dim_b,
            dim_c=dim_c,
            projection=projection,
        )
        rate = detection_rate(counts, inject, dim_c=dim_c)
        rows.append((eps, rate, counts))
    return rows


def scan_point(params):
    (
        eps,
        table_name,
        corr_table_name,
        basis,
        ref_kind,
        inject,
        n_trials,
        seed,
        dim_b,
        dim_c,
        projection,
    ) = params
    rng = np.random.default_rng(seed)
    counts, _ = run_observable(
        table_name,
        corr_table_name,
        basis,
        ref_kind,
        inject,
        eps,
        n_trials,
        rng,
        dim_b=dim_b,
        dim_c=dim_c,
        projection=projection,
    )
    rate = detection_rate(counts, inject, dim_c=dim_c)
    return eps, rate, counts


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--inject",
        default="none",
        choices=["none", "tilt", "curvature", "lines", "dimension"],
    )
    p.add_argument("--epsilon", type=float, default=0.2, help="Injection strength")
    p.add_argument("--dim-b", type=float, default=1.0, help="Dimension injection: b coefficient")
    p.add_argument("--dim-c", type=float, default=0.0, help="Dimension injection: c coefficient")
    p.add_argument("--ref", default="powerlaw_exp", choices=["flat", "powerlaw_exp", "gaussian_lines"])
    p.add_argument("--trials", type=int, default=200)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--spectral", action="store_true", help="Report spectral discreteness stats")
    p.add_argument("--peak-prominence", type=float, default=5.0)
    p.add_argument("--peak-width", type=int, default=1)
    p.add_argument(
        "--peak-baseline",
        choices=["global", "local"],
        default="global",
        help="Baseline for peak detection in spectral discreteness",
    )
    p.add_argument(
        "--peak-baseline-window",
        type=int,
        default=5,
        help="Window for local baseline smoothing (bins)",
    )
    p.add_argument(
        "--spectral-debug",
        action="store_true",
        help="Print spectral threshold diagnostics for the true signal",
    )
    p.add_argument("--scan", action="store_true", help="Scan epsilon and report detection thresholds")
    p.add_argument("--eps-min", type=float, default=0.0)
    p.add_argument("--eps-max", type=float, default=0.6)
    p.add_argument("--eps-steps", type=int, default=7)
    p.add_argument("--projection", choices=["raw", "cumulative"], default="raw")
    p.add_argument("--workers", type=int, default=1, help="Parallel workers for epsilon scans")
    p.add_argument("--only", help="Run a single observable (e.g., pT_yy)")
    return p.parse_args()


def main():
    args = parse_args()
    rng = np.random.default_rng(args.seed)

    print("Pseudo-data harness")
    print(f"inject={args.inject} epsilon={args.epsilon} ref={args.ref} trials={args.trials}")
    spectral_cfg = None
    if args.spectral:
        spectral_cfg = {
            "peak_prominence": args.peak_prominence,
            "peak_width": args.peak_width,
            "baseline_mode": args.peak_baseline,
            "baseline_window": args.peak_baseline_window,
            "debug": args.spectral_debug,
        }
    observables = OBSERVABLES
    if args.only:
        observables = [o for o in OBSERVABLES if o[0] == args.only]
        if not observables:
            raise RuntimeError(f"Unknown observable: {args.only}")
    for table_name, corr_table_name, basis in observables:
        if args.scan and args.inject != "none":
            epsilons = np.linspace(args.eps_min, args.eps_max, args.eps_steps)
            if args.workers > 1:
                seeds = [args.seed + i for i in range(len(epsilons))]
                params = [
                    (
                        eps,
                        table_name,
                        corr_table_name,
                        basis,
                        args.ref,
                        args.inject,
                        args.trials,
                        seed,
                        args.dim_b,
                        args.dim_c,
                        args.projection,
                    )
                    for eps, seed in zip(epsilons, seeds)
                ]
                with mp.Pool(args.workers) as pool:
                    rows = pool.map(scan_point, params)
                rows = sorted(rows, key=lambda row: row[0])
            else:
                rows = scan_epsilons(
                    epsilons,
                    table_name,
                    corr_table_name,
                    basis,
                    args.ref,
                    args.inject,
                    args.trials,
                    rng,
                    dim_b=args.dim_b,
                    dim_c=args.dim_c,
                    projection=args.projection,
                )
            print(f"{table_name:<10} basis={basis:<8} scan eps[{args.eps_min},{args.eps_max}]")
            for eps, rate, _ in rows:
                print(f"  eps={eps:.3f} detect={rate:.2f}")
            eps50 = next((e for e, r, _ in rows if r >= 0.5), None)
            eps90 = next((e for e, r, _ in rows if r >= 0.9), None)
            print(f"  eps50={eps50} eps90={eps90}")
        else:
            counts, spectral = run_observable(
                table_name,
                corr_table_name,
                basis,
                args.ref,
                args.inject,
                args.epsilon,
                args.trials,
                rng,
                spectral_cfg=spectral_cfg,
                dim_b=args.dim_b,
                dim_c=args.dim_c,
                projection=args.projection,
            )
            total = sum(counts.values())
            rates = {k: v / total for k, v in counts.items()}
            print(
                f"{table_name:<10} basis={basis:<8} "
                f"A={rates['A']:.2f} B={rates['B']:.2f} C={rates['C']:.2f}"
            )
            if spectral is not None and spectral["samples"]:
                d_true, peaks_true = spectral["true"]
                d_vals = np.array([v[0] for v in spectral["samples"]], dtype=float)
                p_vals = np.array([v[1] for v in spectral["samples"]], dtype=float)
                print(
                    f"  spectral D_true={d_true:.3f} peaks_true={peaks_true} "
                    f"D_mean={np.mean(d_vals):.3f} D_std={np.std(d_vals):.3f} "
                    f"peaks_mean={np.mean(p_vals):.2f}"
                )
                if spectral.get("debug"):
                    dbg = spectral["debug"]
                    print(
                        f"  spectral debug: max={dbg['max']:.3g} median={dbg['median']:.3g} "
                        f"threshold={dbg['threshold']:.3g} total={dbg['total']:.3g}"
                    )


if __name__ == "__main__":
    main()
