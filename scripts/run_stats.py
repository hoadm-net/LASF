"""
scripts/run_stats.py — Run all statistical tests for the ablation study.

Tests H1, H2, H3 using McNemar's test and Spearman rank correlation.
Reads results from evaluation/results/{dataset}/*.jsonl.

Usage:
    python scripts/run_stats.py --dataset spider_vi
    python scripts/run_stats.py --dataset bird_vi
    python scripts/run_stats.py --dataset spider_vi --alpha 0.05
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from evaluation.stats import run_ablation_stats, run_h3_stats

MODEL_SIZES = {
    "qwen2.5-coder-0.5b": 0.5,
    "qwen2.5-coder-1.5b": 1.5,
    "qwen2.5-coder-3b": 3.0,
    "qwen2.5-coder-7b": 7.0,
}

CONFIGS = ["baseline", "+aug", "+link", "full"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    parser.add_argument("--cfg", default="configs/config.yaml")
    parser.add_argument("--alpha", type=float, default=0.05)
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def config_tag(config: str) -> str:
    return config.replace("+", "plus")


def load_results(results_dir: str, dataset: str) -> dict:
    """
    Load all JSONL results into a nested dict:
    results[model_tag][config] = {"ex_list": [...], "ex": float}
    """
    base_dir = Path(results_dir) / dataset
    results = {}

    for jsonl_path in sorted(base_dir.glob("*.jsonl")):
        records = load_jsonl(jsonl_path)
        if not records:
            continue
        config = records[0]["config"]
        model = records[0]["model"].split("/")[-1].lower().replace("-instruct", "")
        ex_list = [r["execution_accuracy"] for r in records]
        results.setdefault(model, {})[config] = {
            "ex_list": ex_list,
            "ex": sum(ex_list) / len(ex_list),
        }

    return results


def print_mcnemar_results(comparisons: dict, alpha: float) -> None:
    print(f"\n{'─'*60}")
    print("  McNemar's Test (EX)")
    print(f"{'─'*60}")
    print(f"  {'Comparison':<30} {'p-value':>10}  {'Significant':>12}  {'A wins':>8}  {'B wins':>8}")
    print(f"  {'─'*28}  {'─'*8}  {'─'*10}  {'─'*6}  {'─'*6}")
    for label, res in comparisons.items():
        sig = "YES *" if res["significant"] else "no"
        print(
            f"  {label:<30} {res['p_value']:>10.4f}  {sig:>12}  "
            f"{res['a_wins']:>8}  {res['b_wins']:>8}"
        )


def main():
    args = parse_args()
    cfg = load_config(args.cfg)
    results_dir = cfg["evaluation"]["results_dir"]

    all_results = load_results(results_dir, args.dataset)
    if not all_results:
        print(f"No results found in {results_dir}/{args.dataset}/")
        return

    print(f"\n{'='*60}")
    print(f"  Statistical Analysis — {args.dataset.upper()}")
    print(f"  alpha = {args.alpha}")
    print(f"{'='*60}")

    # H1 & H2 per model: McNemar tests
    h3_full_ex, h3_base_ex, h3_sizes = [], [], []

    for model_tag in sorted(all_results.keys()):
        model_res = all_results[model_tag]

        # Only run ablation stats for local Qwen models (need all 4 configs)
        if model_tag not in MODEL_SIZES:
            continue
        missing = [c for c in CONFIGS if c not in model_res]
        if missing:
            print(f"\n  [SKIP] {model_tag}: missing configs {missing}")
            continue

        print(f"\n  Model: {model_tag}")
        comparisons = run_ablation_stats(model_res, alpha=args.alpha)
        print_mcnemar_results(comparisons, args.alpha)

        # Collect for H3
        h3_sizes.append(MODEL_SIZES[model_tag])
        h3_full_ex.append(model_res["full"]["ex"])
        h3_base_ex.append(model_res["baseline"]["ex"])

    # H3: Spearman correlation
    if len(h3_sizes) >= 3:
        print(f"\n{'─'*60}")
        print("  H3 — Spearman Rank Correlation (model size vs delta EX)")
        print(f"{'─'*60}")
        h3 = run_h3_stats(h3_sizes, h3_full_ex, h3_base_ex)

        for size, delta in zip(h3_sizes, h3["deltas"]):
            print(f"  {size}B  delta EX = {delta:+.4f}")
        print(f"\n  rho = {h3['rho']:.4f}  |  p = {h3['p_value']:.4f}  |  "
              f"significant = {'YES *' if h3['significant'] else 'no'}")
        if h3["h3_supported"]:
            print("  → H3 SUPPORTED: smaller models benefit more from schema-aware enhancement.")
        else:
            print("  → H3 NOT SUPPORTED.")
    else:
        print("\n  [INFO] Not enough model sizes to test H3 (need >= 3).")


if __name__ == "__main__":
    main()
