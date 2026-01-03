import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from numpy.linalg import inv

# ----------------------------
# CONFIG
# ----------------------------
HEPDATA_RECORD = "ins1674946"  # ATLAS 13 TeV H→γγ combined differential XS
TABLE_NAME = "Table 1"         # pT(H) differential cross section table

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
        return 0.5 * (x_entry["low"] + x_entry["high"])
    if "value" in x_entry:
        val = x_entry["value"]
        if isinstance(val, str) and "-" in val:
            parts = [p.strip() for p in val.split("-")]
            if len(parts) == 2:
                return 0.5 * (float(parts[0]) + float(parts[1]))
        return float(val)
    raise RuntimeError(f"Unrecognized bin format: {x_entry}")


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


def extract_binned_values(table, data_group=0, ref_group=1):
    """
    Extract bin centers and values.
    Assumes 1D differential XS.
    """
    xs = []
    ys_data = []
    ys_ref = []
    sigmas = []
    bin_centers = []

    for row in table["values"]:
        bin_centers.append(_parse_bin_center(row["x"][0]))
        y_group = {cell.get("group", 0): cell for cell in row["y"]}
        data_cell = y_group.get(data_group)
        ref_cell = y_group.get(ref_group)
        if data_cell is None:
            raise RuntimeError(f"Missing data group {data_group} in row {row}")
        ys_data.append(float(data_cell["value"]))
        sigmas.append(_combine_errors(data_cell.get("errors", [])))
        if ref_cell is not None:
            ys_ref.append(float(ref_cell["value"]))
        else:
            ys_ref.append(float(data_cell["value"]))

    return (
        np.array(bin_centers),
        np.array(ys_data),
        np.array(ys_ref),
        np.array(sigmas),
    )


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
def model_A(params, x, y_sm):
    a = params[0]
    return a * y_sm


def model_B(params, x, y_sm):
    a, b = params
    x0 = np.mean(x)
    return a * y_sm * (1 + b * (x - x0))


def model_C(params, x, y_sm):
    a, b, c = params
    x0 = np.mean(x)
    return a * y_sm * (1 + b * (x - x0) + c * (x - x0) ** 2)


# ----------------------------
# Fit + MDL
# ----------------------------
def chi2(params, model, x, y, y_sm, cov_inv):
    diff = y - model(params, x, y_sm)
    return diff.T @ cov_inv @ diff


def fit_model(model, n_params, x, y, y_sm, cov_inv):
    init = np.ones(n_params)
    res = minimize(
        chi2,
        init,
        args=(model, x, y, y_sm, cov_inv),
        method="Nelder-Mead"
    )
    return res.fun, res.x


def mdl_score(chi2_val, k, n):
    return chi2_val + MDL_LAMBDA * k * np.log(n)


# ----------------------------
# MAIN
# ----------------------------
def main():
    print("Downloading HEPData tables...")

    xs_table = fetch_table(HEPDATA_RECORD, TABLE_NAME)

    x, y, y_sm, sigma = extract_binned_values(xs_table)

    # No correlation matrix provided; assume diagonal covariance.
    cov = np.diag(sigma ** 2)
    cov_inv = inv(cov)

    n = len(y)

    print("\nFitting models...\n")

    chi2_A, pA = fit_model(model_A, 1, x, y, y_sm, cov_inv)
    chi2_B, pB = fit_model(model_B, 2, x, y, y_sm, cov_inv)
    chi2_C, pC = fit_model(model_C, 3, x, y, y_sm, cov_inv)

    mdl_A = mdl_score(chi2_A, 1, n)
    mdl_B = mdl_score(chi2_B, 2, n)
    mdl_C = mdl_score(chi2_C, 3, n)

    print("RESULTS")
    print("--------")
    print(f"Model A (norm only):      chi2={chi2_A:.2f}, MDL={mdl_A:.2f}")
    print(f"Model B (+ tilt):         chi2={chi2_B:.2f}, MDL={mdl_B:.2f}")
    print(f"Model C (+ curvature):    chi2={chi2_C:.2f}, MDL={mdl_C:.2f}")

    print("\nBest model by MDL:")
    best = min(
        [("A", mdl_A), ("B", mdl_B), ("C", mdl_C)],
        key=lambda x: x[1]
    )
    print(f"→ Model {best[0]}")

    print("\nInterpretation:")
    print(
        "If Model A wins → data prefers minimal deformation.\n"
        "If Model B wins → exactly one shape parameter is justified.\n"
        "If Model C wins → higher-order structure is required (would challenge MDL basin picture)."
    )


if __name__ == "__main__":
    main()
