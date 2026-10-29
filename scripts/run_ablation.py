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

sys.path.insert(0, str(Path(__file__).parent.parent))
from run_experiment import result_stem

CONFIGS = ["baseline", "+aug", "+link", "augret", "full"]
LOCAL_MODELS = [
    "Qwen/Qwen2.5-Coder-0.5B-Instruct",
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "Qwen/Qwen2.5-Coder-3B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
]
REFERENCE_MODEL = "gpt-4.1-mini"
REFERENCE_CONFIGS = ["baseline", "full"]
DATASETS = ["spider_vi", "bird_vi"]

# Batch sizes tuned for RTX 3090 (24GB): larger = faster for small models
BATCH_SIZES = {
    "Qwen/Qwen2.5-Coder-0.5B-Instruct": 32,
    "Qwen/Qwen2.5-Coder-1.5B-Instruct": 16,
    "Qwen/Qwen2.5-Coder-3B-Instruct": 8,
    "Qwen/Qwen2.5-Coder-7B-Instruct": 4,
}


# Padded prompt-token budget per batch (RTX 4090, 24GB)
MAX_BATCH_TOKENS = {
    "Qwen/Qwen2.5-Coder-0.5B-Instruct": 131072,
    "Qwen/Qwen2.5-Coder-1.5B-Instruct": 65536,
    "Qwen/Qwen2.5-Coder-3B-Instruct": 49152,
    "Qwen/Qwen2.5-Coder-7B-Instruct": 32768,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=DATASETS, default=None, help="Run for one dataset only")
    parser.add_argument("--model", default=None, help="Run for one local model only")
    parser.add_argument("--cfg", default="configs/config.yaml")
    parser.add_argument("--device", default=None, help="Override device (cpu/cuda)")
    parser.add_argument("--dry_run", action="store_true", help="Print commands without executing")
    parser.add_argument("--overwrite", action="store_true", help="Re-run even if output JSONL exists")
    parser.add_argument("--skip_reference", action="store_true", help="Skip GPT-4.1-mini reference runs")
    parser.add_argument("--configs", nargs="+", default=CONFIGS, choices=CONFIGS, help="Subset of configs")
    parser.add_argument("--lang", choices=["vi", "en"], default="vi")
    parser.add_argument("--top_k", type=int, default=None)
    parser.add_argument("--top_k_ratio", type=float, default=None)
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def output_path(results_dir: str, dataset: str, config: str, model_name: str, args) -> Path:
    stem = result_stem(config, model_name, args.lang, args.top_k, args.top_k_ratio)
    return Path(results_dir) / dataset / f"{stem}.jsonl"


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
    results_dir = cfg["evaluation"]["results_dir_v2"]
    datasets = [args.dataset] if args.dataset else DATASETS
    local_models = [args.model] if args.model else LOCAL_MODELS

    # Build experiment list
    experiments = []

    # Main ablation: local models × all configs × all datasets
    for dataset in datasets:
        for model in local_models:
            for config in args.configs:
                experiments.append((dataset, model, config))

    # GPT-4o-mini upper-bound reference: baseline only
    if not args.skip_reference:
        for dataset in datasets:
            for config in REFERENCE_CONFIGS:
                if config in args.configs:
                    experiments.append((dataset, REFERENCE_MODEL, config))

    total = len(experiments)
    print(f"Total experiments planned: {total}")

    skipped, ran, failed = 0, 0, 0
    for dataset, model, config in experiments:
        out = output_path(results_dir, dataset, config, model, args)

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
        cmd += ["--lang", args.lang]
        if args.top_k is not None:
            cmd += ["--top_k", str(args.top_k)]
        if args.top_k_ratio is not None:
            cmd += ["--top_k_ratio", str(args.top_k_ratio)]
        if args.device:
            cmd += ["--device", args.device]
        if model != REFERENCE_MODEL:
            batch_size = BATCH_SIZES.get(model, 8)
            cmd += ["--batch-size", str(batch_size), "--max_batch_tokens", str(MAX_BATCH_TOKENS.get(model, 32768))]

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
