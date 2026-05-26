"""
scripts/run_eval.py — Convert JSONL predictions to Spider eval format and run official evaluation.

Usage:
    # Evaluate a single JSONL file
    python scripts/run_eval.py --pred evaluation/results/spider_vi/full_qwen2.5-coder-3b.jsonl

    # Evaluate all JSONL files in a directory
    python scripts/run_eval.py --pred_dir evaluation/results/spider_vi

    # Run evaluation and show results table
    python scripts/run_eval.py --pred_dir evaluation/results/spider_vi --summary
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SPIDER_EVAL = Path("third_party/spider/evaluation.py")


def jsonl_to_spider_format(jsonl_path: str, dataset: str) -> tuple[str, str]:
    """
    Convert our JSONL predictions to Spider eval format:
    - gold.sql: one line per example: `<gold_sql>\t<db_id>`
    - pred.sql: one line per example: `<pred_sql>`
    """
    jsonl_path = Path(jsonl_path)
    out_dir = jsonl_path.parent / "spider_format" / jsonl_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    gold_path = out_dir / "gold.sql"
    pred_path = out_dir / "pred.sql"

    with open(jsonl_path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    with open(gold_path, "w", encoding="utf-8") as gf, \
         open(pred_path, "w", encoding="utf-8") as pf:
        for rec in records:
            gold_sql = rec["gold_sql"].strip().rstrip(";")
            pred_sql = rec["pred_sql"].strip().rstrip(";")
            gf.write(f"{gold_sql}\t{rec['db_id']}\n")
            pf.write(f"{pred_sql}\n")

    return str(gold_path), str(pred_path)


def run_spider_eval(gold_path: str, pred_path: str, db_dir: str, table_path: str) -> dict:
    if not SPIDER_EVAL.exists():
        print("Spider eval scripts not found. Run: python scripts/setup_eval.py")
        sys.exit(1)

    cmd = [
        sys.executable, str(SPIDER_EVAL),
        "--gold", gold_path,
        "--pred", pred_path,
        "--etype", "all",
        "--db", db_dir,
        "--table", table_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
    return {"stdout": result.stdout, "returncode": result.returncode}


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pred", help="Path to a single JSONL predictions file")
    group.add_argument("--pred_dir", help="Directory containing JSONL prediction files")
    parser.add_argument("--dataset", choices=["spider_vi", "bird_vi"], default="spider_vi")
    parser.add_argument("--cfg", default="configs/config.yaml")
    args = parser.parse_args()

    import yaml
    with open(args.cfg) as f:
        cfg = yaml.safe_load(f)

    db_dir = cfg["data"][args.dataset]["db_dir"]
    table_path = str(Path(cfg["data"][args.dataset]["dev"]).parent / "tables.json")

    files = []
    if args.pred:
        files = [args.pred]
    elif args.pred_dir:
        files = sorted(Path(args.pred_dir).glob("*.jsonl"))

    for pred_file in files:
        print(f"\n{'='*60}")
        print(f"Evaluating: {pred_file}")
        print('='*60)
        gold_path, pred_path = jsonl_to_spider_format(str(pred_file), args.dataset)
        run_spider_eval(gold_path, pred_path, db_dir, table_path)


if __name__ == "__main__":
    main()
