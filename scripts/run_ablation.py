"""
scripts/run_ablation.py — Orchestrate all ablation experiments.

Runs all combinations of dataset × config × model, then the GPT-4o-mini
upper-bound reference baseline. Skips experiments whose output JSONL already exists.

Usage:
    # Full ablation (all datasets, all models, all configs)
    python scripts/run_ablation.py

    # Single dataset
    python scripts/run_ablation.py --dataset spider_vi

    # Single model (useful for quick testing)
    python scripts/run_ablation.py --model Qwen/Qwen2.5-Coder-3B-Instruct

    # Dry-run: print what would be executed without running
    python scripts/run_ablation.py --dry_run

    # Override device
    python scripts/run_ablation.py --device cuda
"""

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

CONFIGS = ["baseline", "+aug", "+link", "full"]
LOCAL_MODELS = [
    "Qwen/Qwen2.5-Coder-0.5B-Instruct",
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "Qwen/Qwen2.5-Coder-3B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
]
REFERENCE_MODEL = "gpt-4.1-mini"
REFERENCE_CONFIGS = ["baseline"]
DATASETS = ["spider_vi", "bird_vi"]

# Batch sizes tuned for RTX 3090 (24GB): larger = faster for small models
BATCH_SIZES = {
    "Qwen/Qwen2.5-Coder-0.5B-Instruct": 32,
    "Qwen/Qwen2.5-Coder-1.5B-Instruct": 16,
    "Qwen/Qwen2.5-Coder-3B-Instruct": 8,
    "Qwen/Qwen2.5-Coder-7B-Instruct": 4,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=DATASETS, default=None, help="Run for one dataset only")
    parser.add_argument("--model", default=None, help="Run for one local model only")
    parser.add_argument("--cfg", default="configs/config.yaml")
    parser.add_argument("--device", default=None, help="Override device (cpu/cuda)")
    parser.add_argument("--dry_run", action="store_true", help="Print commands without executing")
    parser.add_argument("--overwrite", action="store_true", help="Re-run even if output JSONL exists")
    parser.add_argument("--skip_reference", action="store_true", help="Skip GPT-4o-mini reference baseline")
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def output_path(results_dir: str, dataset: str, config: str, model_name: str) -> Path:
    model_tag = model_name.split("/")[-1].lower().replace("-instruct", "")
    config_tag = config.replace("+", "plus")
    return Path(results_dir) / dataset / f"{config_tag}_{model_tag}.jsonl"


def run_experiment(cmd: list[str], dry_run: bool) -> bool:
    print(f"\n{'─'*60}")
    print("  " + " ".join(cmd))
    print(f"{'─'*60}")
    if dry_run:
        return True
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    args = parse_args()
    cfg = load_config(args.cfg)
    results_dir = cfg["evaluation"]["results_dir"]
    datasets = [args.dataset] if args.dataset else DATASETS
    local_models = [args.model] if args.model else LOCAL_MODELS

    # Build experiment list
    experiments = []

    # Main ablation: local models × all configs × all datasets
    for dataset in datasets:
        for model in local_models:
            for config in CONFIGS:
                experiments.append((dataset, model, config))

    # GPT-4o-mini upper-bound reference: baseline only
    if not args.skip_reference:
        for dataset in datasets:
            for config in REFERENCE_CONFIGS:
                experiments.append((dataset, REFERENCE_MODEL, config))

    total = len(experiments)
    print(f"Total experiments planned: {total}")

    skipped, ran, failed = 0, 0, 0
    for dataset, model, config in experiments:
        out = output_path(results_dir, dataset, config, model)

        if out.exists() and not args.overwrite:
            print(f"  [SKIP] {out.name} already exists.")
            skipped += 1
            continue

        cmd = [
            sys.executable, "run_experiment.py",
            "--dataset", dataset,
            "--model", model,
            "--config", config,
            "--cfg", args.cfg,
        ]
        if args.device:
            cmd += ["--device", args.device]
        if model != REFERENCE_MODEL:
            batch_size = BATCH_SIZES.get(model, 8)
            cmd += ["--batch-size", str(batch_size)]

        ok = run_experiment(cmd, args.dry_run)
        if ok:
            ran += 1
        else:
            failed += 1
            print(f"  [FAILED] {dataset} | {config} | {model}")

    print(f"\n{'='*60}")
    print(f"  Done. Ran: {ran} | Skipped: {skipped} | Failed: {failed} | Total: {total}")
    if args.dry_run:
        print("  (dry-run — no experiments were actually executed)")


if __name__ == "__main__":
    main()
