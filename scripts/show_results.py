"""
scripts/show_results.py — Print a results table from all JSONL prediction files.

Displays EM and EX per config × model, grouped by dataset.

Usage:
    python scripts/show_results.py
    python scripts/show_results.py --dataset spider_vi
    python scripts/show_results.py --metric ex        # show EX only
"""

import argparse
import json
from pathlib import Path

import yaml

CONFIGS_ORDER = ["baseline", "+aug", "+link", "full"]
MODEL_ORDER = [
    "qwen2.5-coder-0.5b",
    "qwen2.5-coder-1.5b",
    "qwen2.5-coder-3b",
    "qwen2.5-coder-7b",
    "gpt-4.1-mini",   # reference
]
DATASETS = ["spider_vi", "bird_vi"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=DATASETS, default=None)
    parser.add_argument("--metric", choices=["em", "ex", "both"], default="both")
    parser.add_argument("--cfg", default="configs/config.yaml")
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_results(results_dir: str, dataset: str) -> dict:
    """Returns results[model_tag][config] = {"em": float, "ex": float, "n": int}"""
    base_dir = Path(results_dir) / dataset
    results = {}
    for jsonl_path in sorted(base_dir.glob("*.jsonl")):
        records = load_jsonl(jsonl_path)
        if not records:
            continue
        config = records[0]["config"]
        model = records[0]["model"].split("/")[-1].lower().replace("-instruct", "")
        n = len(records)
        em = sum(r["exact_match"] for r in records) / n
        ex = sum(r["execution_accuracy"] for r in records) / n
        results.setdefault(model, {})[config] = {"em": em, "ex": ex, "n": n}
    return results


def cell(val: float | None) -> str:
    if val is None:
        return "  —   "
    return f"{val*100:5.1f}%"


def print_table(dataset: str, results: dict, metric: str) -> None:
    metrics = ["em", "ex"] if metric == "both" else [metric]

    # Determine model order (present only)
    models = [m for m in MODEL_ORDER if m in results]
    models += [m for m in results if m not in MODEL_ORDER]  # catch any unlisted models

    col_w = 12
    header_model = f"{'Model':<26}"
    header_configs = ""
    for cfg in CONFIGS_ORDER:
        if metric == "both":
            header_configs += f"{'':>{col_w - 6}}{cfg:<6}(EM / EX)   "
        else:
            header_configs += f"  {cfg:<14}"

    print(f"\n{'='*70}")
    print(f"  Dataset: {dataset.upper()}")
    print(f"{'='*70}")

    # Header row
    if metric == "both":
        print(f"  {'Model':<26}", end="")
        for cfg in CONFIGS_ORDER:
            print(f"  {cfg:^18}", end="")
        print()
        print(f"  {'':<26}", end="")
        for _ in CONFIGS_ORDER:
            print(f"  {'EM':>7}  {'EX':>7}  ", end="")
        print()
    else:
        print(f"  {'Model':<26}", end="")
        for cfg in CONFIGS_ORDER:
            print(f"  {cfg:>9}", end="")
        print(f"  {'('+metric.upper()+')':>5}")

    print(f"  {'─'*26}", end="")
    for _ in CONFIGS_ORDER:
        print(f"  {'─'*17}", end="")
    print()

    # Data rows
    for model in models:
        is_ref = model == "gpt-4o-mini"
        label = f"  {'*' if is_ref else ' '}{model:<25}"
        print(label, end="")
        for cfg in CONFIGS_ORDER:
            data = results[model].get(cfg)
            if metric == "both":
                em_val = cell(data["em"] if data else None)
                ex_val = cell(data["ex"] if data else None)
                print(f"  {em_val} {ex_val}  ", end="")
            else:
                val = cell(data[metric] if data else None)
                print(f"  {val:>9}", end="")
        print()

    if any(m == "gpt-4.1-mini" for m in models):
        print(f"\n  * GPT-4.1-mini = upper-bound reference baseline (baseline config only)")


def main():
    args = parse_args()
    cfg = load_config(args.cfg)
    results_dir = cfg["evaluation"]["results_dir"]
    datasets = [args.dataset] if args.dataset else DATASETS

    any_results = False
    for dataset in datasets:
        results = load_results(results_dir, dataset)
        if not results:
            print(f"  No results found for {dataset}.")
            continue
        any_results = True
        print_table(dataset, results, args.metric)

    if not any_results:
        print(f"\nNo results found in '{results_dir}/'. Run experiments first.")


if __name__ == "__main__":
    main()
