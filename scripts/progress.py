"""
Quick progress tracker: shows which ablation experiments are done / pending / failed.
Usage: python scripts/progress.py [--watch]
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATASETS = ["spider_vi", "bird_vi"]
LOCAL_MODELS = [
    "Qwen/Qwen2.5-Coder-0.5B-Instruct",
    "Qwen/Qwen2.5-Coder-1.5B-Instruct",
    "Qwen/Qwen2.5-Coder-3B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
]
CONFIGS = ["baseline", "+aug", "+link", "full"]
GPT_MODEL = "gpt-4.1-mini"
GPT_CONFIGS = ["baseline"]

RESULTS_DIR = Path("evaluation/results")
LOG_FILE = Path("/tmp/ablation_spider.log")


def short_model(model: str) -> str:
    return model.split("/")[-1].replace("Qwen2.5-Coder-", "").replace("-Instruct", "")


def result_path(dataset: str, model: str, config: str) -> Path:
    safe = model.replace("/", "__")
    return RESULTS_DIR / dataset / f"{safe}__{config}.jsonl"


def count_lines(p: Path) -> int:
    try:
        return sum(1 for _ in p.open())
    except Exception:
        return 0


def render(dataset: str) -> None:
    all_experiments = []
    for m in LOCAL_MODELS:
        for c in CONFIGS:
            all_experiments.append((m, c))
    all_experiments.append((GPT_MODEL, "baseline"))

    done, pending = 0, 0

    col_w = 26
    header = f"{'Model':<14} | " + " | ".join(f"{c:^9}" for c in CONFIGS) + " | GPT-mini"
    print(f"\n  Dataset: {dataset}")
    print("  " + "-" * len(header))
    print("  " + header)
    print("  " + "-" * len(header))

    for m in LOCAL_MODELS:
        cells = []
        for c in CONFIGS:
            p = result_path(dataset, m, c)
            if p.exists():
                n = count_lines(p)
                cells.append(f"  ✓{n:>4} ")
                done += 1
            else:
                cells.append("  ·····  ")
                pending += 1
        row = f"  {short_model(m):<14}| " + " | ".join(cells)
        print(row)

    # GPT row
    p_gpt = result_path(dataset, GPT_MODEL, "baseline")
    gpt_cell = f"✓{count_lines(p_gpt):>4}" if p_gpt.exists() else "·····"
    if p_gpt.exists():
        done += 1
    else:
        pending += 1
    print("  " + "-" * len(header))
    print(f"  {'gpt-4.1-mini':<14}|           |           |           |           | {gpt_cell}")

    total = done + pending
    bar_len = 30
    filled = int(bar_len * done / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = 100 * done // total if total else 0
    print(f"\n  Progress: [{bar}] {done}/{total} ({pct}%)\n")


def tail_log(n: int = 5) -> None:
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text().splitlines()
        recent = [l for l in lines[-50:] if l.strip() and not l.startswith("  /venv")]
        print("  Recent log:")
        for l in recent[-n:]:
            print("    " + l)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="spider_vi")
    parser.add_argument("--watch", action="store_true", help="Refresh every 30s")
    args = parser.parse_args()

    while True:
        if args.watch:
            os.system("clear")
        render(args.dataset)
        if args.watch:
            tail_log()
            print("  [Ctrl+C to stop, refreshing every 30s]")
            try:
                time.sleep(30)
            except KeyboardInterrupt:
                break
        else:
            break


if __name__ == "__main__":
    main()
