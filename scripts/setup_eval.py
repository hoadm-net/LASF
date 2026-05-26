"""
scripts/setup_eval.py — Download Spider official evaluation scripts.

Run once after cloning the repo:
    python scripts/setup_eval.py
"""

import subprocess
from pathlib import Path

SPIDER_EVAL_FILES = {
    "evaluation.py": "https://raw.githubusercontent.com/taoyds/spider/master/evaluation.py",
    "process_sql.py": "https://raw.githubusercontent.com/taoyds/spider/master/process_sql.py",
}

OUT_DIR = Path("third_party/spider")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename, url in SPIDER_EVAL_FILES.items():
        out_path = OUT_DIR / filename
        if out_path.exists():
            print(f"  {filename} already exists, skipping.")
            continue
        print(f"  Downloading {filename}...")
        result = subprocess.run(["curl", "-sL", url, "-o", str(out_path)], capture_output=True)
        if result.returncode == 0:
            print(f"  Saved → {out_path}")
        else:
            print(f"  ERROR downloading {filename}: {result.stderr.decode()}")

    print("\nSpider eval scripts ready in third_party/spider/")
    print("Usage:")
    print("  python third_party/spider/evaluation.py \\")
    print("    --gold data/spider_vi/gold.sql \\")
    print("    --pred evaluation/results/spider_vi/pred.sql \\")
    print("    --etype all \\")
    print("    --db data/spider_vi/database \\")
    print("    --table data/spider_vi/tables.json")


if __name__ == "__main__":
    main()
