import numpy as np
from scipy.stats import binomtest, chi2


def mcnemar_test(list_a: list[int], list_b: list[int], exact_below: int = 25) -> dict:
    """
    McNemar's test on paired binary outcomes (A vs B on the same questions).
    Exact binomial test when the number of discordant pairs is below `exact_below`,
    otherwise the chi-square test with continuity correction.
    """
    a, b = np.asarray(list_a), np.asarray(list_b)
    assert len(a) == len(b), "Lists must have equal length"
    a_only = int(((a == 1) & (b == 0)).sum())
    b_only = int(((a == 0) & (b == 1)).sum())
    n_disc = a_only + b_only
    if n_disc == 0:
        return {"a_only": 0, "b_only": 0, "test": "none", "statistic": 0.0, "p_value": 1.0}
    if n_disc < exact_below:
        return {"a_only": a_only, "b_only": b_only, "test": "exact",
                "statistic": float(min(a_only, b_only)),
                "p_value": float(binomtest(a_only, n_disc, 0.5).pvalue)}
    stat = (abs(a_only - b_only) - 1) ** 2 / n_disc
    return {"a_only": a_only, "b_only": b_only, "test": "chi2_cc",
            "statistic": float(stat), "p_value": float(chi2.sf(stat, 1))}


def holm(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adjusted[i] = min(1.0, running)
    return adjusted.tolist()


def paired_bootstrap_ci(list_a: list[int], list_b: list[int], n_boot: int = 10_000,
                        alpha: float = 0.05, seed: int = 2026) -> tuple[float, float]:
    """Percentile CI for mean(A) - mean(B), resampling questions with replacement."""
    diff = np.asarray(list_a, dtype=float) - np.asarray(list_b, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for start in range(0, n_boot, 1000):  # chunks keep memory small for n ~ 1.5k
        idx = rng.integers(0, len(diff), size=(min(1000, n_boot - start), len(diff)))
        means[start:start + len(idx)] = diff[idx].mean(axis=1)
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)
