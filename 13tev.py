import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from numpy.linalg import inv

# ----------------------------
# CONFIG
# ----------------------------
HEPDATA_RECORD = "ins2073877"  # CMS 13.6 TeV H→γγ differential XS
OBSERVABLE_TABLE = 1          # pT(H) differential cross section table
CORR_TABLE = 2                # correlation matrix table

MDL_LAMBDA = 1.0  # strength of MDL penalty


# ----------------------------
# HEPData helpers
# ----------------------------
def fetch_table(record, table_id):
    url = f"https://www.hepdata.net/record/{record}?format=json"
    data = _get_json(url, context="record")
    table = data["tables"][table_id]
    table_url = "https://www.hepdata.net" + table["location"]
    table_data = _get_json(table_url + "?format=json", context="table")
    return table_data


def extract_binned_values(table):
    """
    Extract bin centers and values.
    Assumes 1D differential XS.
    """
    xs = []
    bin_centers = []

    for row in table["values"]:
        low = row["x"][0]["low"]
        high = row["x"][0]["high"]
        val = row["y"][0]["value"]

        bin_centers.append(0.5 * (low + high))
        xs.append(val)

    return np.array(bin_centers), np.array(xs)


def extract_correlation_matrix(table):
    """
    Extract correlation matrix from HEPData table.
    """
    n = len(table["values"])
    corr = np.zeros((n, n))

    for i, row in enumerate(table["values"]):
        for j, cell in enumerate(row["y"]):
            corr[i, j] = cell["value"]

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

    xs_table = fetch_table(HEPDATA_RECORD, OBSERVABLE_TABLE)
    corr_table = fetch_table(HEPDATA_RECORD, CORR_TABLE)

    x, y = extract_binned_values(xs_table)
    corr = extract_correlation_matrix(corr_table)

    # crude uncertainty estimate from diagonal if not provided
    sigma = 0.1 * y  # conservative 10%
    cov = np.outer(sigma, sigma) * corr
    cov_inv = inv(cov)

    # SM reference = measured central values (null deformation test)
    y_sm = y.copy()

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
