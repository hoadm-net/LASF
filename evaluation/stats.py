import numpy as np
from scipy.stats import spearmanr
from statsmodels.stats.contingency_tables import mcnemar


def mcnemar_test(list_a: list[int], list_b: list[int]) -> dict:
    """
    McNemar's test comparing two binary outcome lists.
    list_a: binary results of system A (e.g., +Aug)
    list_b: binary results of system B (e.g., Baseline)
    """
    assert len(list_a) == len(list_b), "Lists must have equal length"

    # Contingency table
    # [A correct & B correct, A correct & B wrong]
    # [A wrong & B correct,   A wrong & B wrong  ]
    b = sum(1 for a, b in zip(list_a, list_b) if a == 1 and b == 0)  # A wins
    c = sum(1 for a, b in zip(list_a, list_b) if a == 0 and b == 1)  # B wins

    table = [[0, b], [c, 0]]
    result = mcnemar(table, exact=False, correction=True)

    return {
        "statistic": result.statistic,
        "p_value": result.pvalue,
        "a_wins": b,
        "b_wins": c,
        "significant": result.pvalue < 0.05,
    }


def spearman_correlation(model_sizes: list[float], deltas: list[float]) -> dict:
    """
    Spearman's rank correlation between model size and delta EX.
    model_sizes: e.g., [0.5, 1.5, 3.0, 7.0]
    deltas:      delta EX for each model size (Full - Baseline)
    """
    corr, p_value = spearmanr(model_sizes, deltas)
    return {
        "rho": corr,
        "p_value": p_value,
        "significant": p_value < 0.05,
        "h3_supported": corr < 0 and p_value < 0.05,
    }


def run_ablation_stats(results: dict, alpha: float = 0.05) -> dict:
    """
    Run all statistical tests for the ablation study.

    results: {
        "baseline": {"ex_list": [...], "ex": 0.xx},
        "+aug":     {"ex_list": [...], "ex": 0.xx},
        "+link":    {"ex_list": [...], "ex": 0.xx},
        "full":     {"ex_list": [...], "ex": 0.xx},
    }
    Returns summary of all comparisons.
    """
    baseline = results["baseline"]["ex_list"]
    comparisons = {}

    for config in ["+aug", "+link", "full"]:
        comparisons[f"{config}_vs_baseline"] = mcnemar_test(
            results[config]["ex_list"], baseline
        )

    return comparisons


def run_h3_stats(model_sizes: list[float], full_ex: list[float], baseline_ex: list[float]) -> dict:
    """
    Test H3: smaller models benefit more from schema-aware enhancement.

    model_sizes:  [0.5, 1.5, 3.0, 7.0]
    full_ex:      EX of Full config per model size
    baseline_ex:  EX of Baseline per model size
    """
    deltas = [f - b for f, b in zip(full_ex, baseline_ex)]
    result = spearman_correlation(model_sizes, deltas)
    result["deltas"] = deltas
    return result
