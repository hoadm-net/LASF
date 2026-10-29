"""
augmentation/generate_aug.py — Offline script: augment all database schemas in a dataset.

Run once before any experiment. Skips schemas that already have an augmented JSON file.

Usage:
    python augmentation/generate_aug.py --dataset spider_vi
    python augmentation/generate_aug.py --dataset bird_vi
    python augmentation/generate_aug.py --dataset spider_vi --device cuda
    python augmentation/generate_aug.py --dataset spider_vi --db_id concert_singer  # single DB
"""

import argparse
import json
import platform
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from tqdm import tqdm

from utils.data_loader import load_schema_from_db
from augmentation.augmentor import SchemaAugmentor


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    parser.add_argument("--cfg", default="configs/config.yaml")
    parser.add_argument("--device", default=None, help="Override device (cpu/cuda)")
    parser.add_argument("--db_id", default=None, help="Augment a single database by id (for debugging)")
    parser.add_argument("--overwrite", action="store_true", help="Re-augment even if JSON already exists")
    parser.add_argument("--seed", type=int, default=None, help="Override augmentation.seed from config")
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_unique_db_ids(dev_path: str) -> list[str]:
    with open(dev_path, encoding="utf-8") as f:
        data = json.load(f)
    seen = set()
    ids = []
    for item in data:
        db_id = item["db_id"]
        if db_id not in seen:
            seen.add(db_id)
            ids.append(db_id)
    return ids


def main():
    args = parse_args()
    cfg = load_config(args.cfg)

    aug_cfg = cfg["augmentation"]
    device = args.device or aug_cfg["device"]
    output_dir = aug_cfg["output_dir"]

    dataset_cfg = cfg["data"][args.dataset]
    dev_path = dataset_cfg["dev"]
    db_dir = dataset_cfg["db_dir"]

    # Determine which DBs to process
    if args.db_id:
        db_ids = [args.db_id]
    else:
        db_ids = get_unique_db_ids(dev_path)

    print(f"Dataset   : {args.dataset}")
    print(f"DBs found : {len(db_ids)}")
    print(f"Output dir: {output_dir}")
    print(f"Device    : {device}")
    print()

    # Filter already-done unless --overwrite
    if not args.overwrite:
        pending = [d for d in db_ids if not (Path(output_dir) / f"{d}.json").exists()]
        skipped = len(db_ids) - len(pending)
        if skipped:
            print(f"Skipping {skipped} already-augmented schemas (use --overwrite to redo).")
        db_ids = pending

    if not db_ids:
        print("All schemas already augmented. Nothing to do.")
        return

    # Load augmentor (loads model once)
    seed = args.seed if args.seed is not None else aug_cfg.get("seed", 2026)
    augmentor = SchemaAugmentor(
        model_name=aug_cfg["model"],
        device=device,
        max_retries=aug_cfg["max_retries"],
        seed=seed,
        max_new_tokens=aug_cfg.get("max_new_tokens", 1024),
    )

    # Cost log for the offline step (one line per DB), used to report augmentation cost
    import torch
    import transformers
    stats_path = Path(output_dir) / f"_stats_{args.dataset}.jsonl"
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else platform.processor()

    success, failed = 0, []
    for db_id in tqdm(db_ids, desc="Augmenting schemas"):
        db_path = str(Path(db_dir) / db_id / f"{db_id}.sqlite")
        try:
            schema = load_schema_from_db(db_path, db_id)
            if torch.cuda.is_available():
                torch.cuda.reset_peak_memory_stats()
            start = time.perf_counter()
            augmented = augmentor.augment_schema(schema)
            seconds = time.perf_counter() - start
            augmentor.save(augmented, output_dir)
            ts = augmentor.table_stats
            record = {
                "db_id": db_id,
                "n_tables": len(schema.tables),
                "n_columns": sum(len(t.columns) for t in schema.tables),
                "seconds": round(seconds, 2),
                "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2) if torch.cuda.is_available() else None,
                "attempts": sum(t["attempts"] for t in ts),
                "failed_tables": [t["table"] for t in ts if not t["ok"]],
                "prompt_tokens": sum(t["prompt_tokens"] for t in ts),
                "output_tokens": sum(t["output_tokens"] for t in ts),
                "model": aug_cfg["model"],
                "seed": seed,
                "gpu": gpu,
                "torch": torch.__version__,
                "transformers": transformers.__version__,
            }
            with open(stats_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            success += 1
        except Exception as e:
            print(f"\n[ERROR] {db_id}: {e}")
            failed.append(db_id)

    print(f"\nDone. Success: {success} | Failed: {len(failed)}")
    if failed:
        print(f"Failed DBs: {failed}")


if __name__ == "__main__":
    main()
