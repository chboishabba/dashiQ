"""
MDL shape-complexity test on unfolded differential spectra (Path C framing).

We use full published covariance and do not assume an SM/theory baseline. The
question is: how many functional degrees of freedom are justified by the data
itself once correlations are respected?

We use a positive deformation family over a chosen basis:

    y(x) = exp(log_a + b u + c u^2) * y_ref(x),   u = basis(x)

Model A: normalization only (log_a)
Model B: + log-slope (b)
Model C: + curvature (c)

Here y_ref(x) = 1 (flat baseline), so A/B/C measure shape complexity rather
than SM-relative deviations. For continuous scale-like spectra we use log
basis u = log(x/x0); for bounded continuous spectra we use linear basis
u = x - x0. Different observables can justify different complexities under
the same MDL criterion.

Note: for discrete/ordinal observables (e.g., jet counts), alternative bases
may be more natural; we treat that as a follow-up sensitivity study.
"""

import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from numpy.linalg import inv

# ----------------------------
# CONFIG
# ----------------------------
HEPDATA_RECORD = "137886"  # ATLAS 13 TeV H→γγ differential XS
OBSERVABLES = [
    ("pT_yy", "pT_yy_corr", "log"),
    ("yAbs_yy", "yAbs_yy_corr", "linear"),
    ("N_j_30", "N_j_30_corr", "log"),
    ("N_j_30", "N_j_30_corr", "ordinal"),
]

MDL_LAMBDA = 1.0  # strength of MDL penalty


# ----------------------------
# HEPData helpers
# ----------------------------
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
        if isinstance(val, str) and "-" in val:
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
    """
    Extract bin centers and values.
    Assumes 1D differential XS.
    """
    xs = []
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


def _get_json(url, context="resource"):
    resp = requests.get(
        url,
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    try:
        return resp.json()
    except requests.exceptions.JSONDecodeError as exc:
        snippet = resp.text[:200].replace("\n", " ").strip()
        raise RuntimeError(
            f"Unexpected non-JSON response while fetching {context} from {url}: "
            f"content-type={resp.headers.get('content-type')!r}, "
            f"snippet={snippet!r}"
        ) from exc


# ----------------------------
# Models
# ----------------------------
def _basis(x, basis):
    x0 = np.mean(x)
    if basis == "log":
        return np.log(x / x0)
    if basis == "linear":
        return x - x0
    if basis == "ordinal":
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


# ----------------------------
# Fit + MDL
# ----------------------------
def chi2(params, model, x, y, y_sm, cov_inv, basis):
    diff = y - model(params, x, y_sm, basis)
    return diff.T @ cov_inv @ diff


def fit_model(model, n_params, x, y, y_sm, cov_inv, basis):
    init = np.zeros(n_params)
    init[0] = np.log(np.mean(y))
    res = minimize(
        chi2,
        init,
        args=(model, x, y, y_sm, cov_inv, basis),
        method="Nelder-Mead"
    )
    return res.fun, res.x


def mdl_score(chi2_val, k, n):
    return chi2_val + MDL_LAMBDA * k * np.log(n)


# ----------------------------
# MAIN
# ----------------------------
def run_one(table_name, corr_table_name, basis):
    xs_table = fetch_table(HEPDATA_RECORD, table_name)
    corr_table = fetch_table(HEPDATA_RECORD, corr_table_name)

    x, y, sigma, bin_edges, is_categorical = extract_binned_values(xs_table)
    if basis == "ordinal" or is_categorical:
        x = np.arange(1, len(x) + 1, dtype=float)
    elif basis == "log" and np.any(x <= 0):
        raise RuntimeError(
            f"{table_name} has non-positive x for log basis; use linear/ordinal."
        )
    corr = extract_correlation_matrix(corr_table, bin_edges)
    cov = np.outer(sigma, sigma) * corr
    cov_inv = inv(cov)

    # Use a flat baseline; models represent increasing shape complexity.
    y_ref = np.ones_like(y)

    n = len(y)

    chi2_A, _ = fit_model(model_A, 1, x, y, y_ref, cov_inv, basis)
    chi2_B, _ = fit_model(model_B, 2, x, y, y_ref, cov_inv, basis)
    chi2_C, _ = fit_model(model_C, 3, x, y, y_ref, cov_inv, basis)

    mdl_A = mdl_score(chi2_A, 1, n)
    mdl_B = mdl_score(chi2_B, 2, n)
    mdl_C = mdl_score(chi2_C, 3, n)

    return (chi2_A, mdl_A), (chi2_B, mdl_B), (chi2_C, mdl_C)


def main():
    print("Downloading HEPData tables...")

    locked = []
    atlas_rows = []
    for table_name, corr_table_name, basis in OBSERVABLES:
        print(f"\n=== Observable: {table_name} (corr: {corr_table_name}) ===")
        try:
            (chi2_A, mdl_A), (chi2_B, mdl_B), (chi2_C, mdl_C) = run_one(
                table_name,
                corr_table_name,
                basis,
            )
        except RuntimeError as exc:
            print(f"Skipping {table_name}: {exc}")
            continue

        print("RESULTS")
        print("--------")
        print(f"Model A (norm only):      chi2={chi2_A:.2f}, MDL={mdl_A:.2f}")
        print(f"Model B (+ tilt):         chi2={chi2_B:.2f}, MDL={mdl_B:.2f}")
        print(f"Model C (+ curvature):    chi2={chi2_C:.2f}, MDL={mdl_C:.2f}")
        best_mdl = min(mdl_A, mdl_B, mdl_C)
        print(
            "ΔMDL(A,B,C) = "
            f"{mdl_A-best_mdl:.2f}, "
            f"{mdl_B-best_mdl:.2f}, "
            f"{mdl_C-best_mdl:.2f}"
        )

        best = min(
            [("A", mdl_A), ("B", mdl_B), ("C", mdl_C)],
            key=lambda x: x[1]
        )
        print(f"→ Best by MDL: Model {best[0]}")
        if basis == "log":
            locked.append((table_name, best[0]))

        mdls = {"A": mdl_A, "B": mdl_B, "C": mdl_C}
        sorted_mdls = sorted(mdls.items(), key=lambda kv: kv[1])
        margin = sorted_mdls[1][1] - sorted_mdls[0][1]
        if best[0] == "A":
            detail = "normalization only"
        elif best[0] == "B":
            detail = "one shape DOF"
        else:
            detail = "curvature"
        if margin < 1.0:
            strength = "weak"
        elif margin < 3.0:
            strength = "moderate"
        else:
            strength = "strong"
        atlas_rows.append((table_name, basis, best[0], margin, detail, strength))

    if locked:
        print("\nLocked Path C result (full covariance):")
        for table_name, best in locked:
            if best == "A":
                detail = "normalization only"
            elif best == "B":
                detail = "one shape DOF (tilt)"
            else:
                detail = "curvature"
            print(f"- {table_name}: Model {best} ({detail})")
        print("Conclusion: minimal shape complexity is observable-dependent under full covariance.")

    if atlas_rows:
        print("\nCOMPLEXITY ATLAS (MDL, full covariance)")
        print("observable   basis    best   margin   notes")
        for table_name, basis, best, margin, detail, strength in atlas_rows:
            notes = f"{detail}; {strength} preference"
            print(f"{table_name:<11} {basis:<8} {best:<5} {margin:>6.2f}   {notes}")


if __name__ == "__main__":
    main()
