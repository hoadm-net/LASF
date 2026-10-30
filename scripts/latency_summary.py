"""
scripts/latency_summary.py — Cost of each pipeline stage (E8).

Online: per-question schema linking and SQL generation time (batch size 1, 200 sampled
questions), peak GPU memory and prompt length, for baseline and full.
Offline: augmentation time and peak memory per dataset; LLM table selection (E7) cost.

Usage:
    python scripts/latency_summary.py

Output: evaluation/analysis_v2/latency/summary.csv and offline.csv
"""

import csv
import json
from pathlib import Path

import numpy as np

LAT = Path("evaluation/analysis_v2/latency")


def main():
    rows = []
    for meta_path in sorted(LAT.glob("*/*.meta.json")):
        meta = json.loads(meta_path.read_text())
        recs = [json.loads(l) for l in open(meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl")))]
        gen = np.array([float(r["gen_ms"]) for r in recs])
        link = np.array([float(r["link_ms"] or 0) for r in recs])
        total = gen + link
        rows.append({
            "dataset": meta_path.parent.name, "config": meta["args"]["config"],
            "model": meta["args"]["model"].split("/")[-1], "n": len(recs),
            "link_ms_p50": round(np.median(link), 1), "gen_ms_p50": round(np.median(gen), 1),
            "total_ms_p50": round(np.median(total), 1), "total_ms_p95": round(np.percentile(total, 95), 1),
            "prompt_tokens_mean": round(np.mean([int(r["prompt_tokens"]) for r in recs]), 1),
            "output_tokens_mean": round(np.mean([int(r.get("output_tokens") or 0) for r in recs]), 1),
            "peak_vram_gb": meta.get("peak_vram_gb"),
            "ex_sample": round(np.mean([int(r["execution_accuracy"]) for r in recs]), 4),
        })
    with open(LAT / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    offline = []
    for stats in sorted(Path("augmentation/augmented_schemas").glob("_stats_*.jsonl")):
        recs = [json.loads(l) for l in open(stats)]
        offline.append({"stage": "augmentation", "dataset": stats.stem.replace("_stats_", ""), "n_db": len(recs),
                        "seconds": round(sum(r["seconds"] for r in recs), 1),
                        "peak_vram_gb": max(r["peak_vram_gb"] for r in recs),
                        "seconds_per_db_max": round(max(r["seconds"] for r in recs), 1)})
    for meta_path in sorted(Path("evaluation/analysis_v2/llm_selection").glob("*.meta.json")):
        m = json.loads(meta_path.read_text())
        offline.append({"stage": "llm_table_selection", "dataset": meta_path.name.split(".")[0], "n_db": "",
                        "seconds": m["seconds"], "peak_vram_gb": m["peak_vram_gb"],
                        "seconds_per_db_max": "", "ms_per_question": m["ms_per_question"]})
    with open(LAT / "offline.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "dataset", "n_db", "seconds", "peak_vram_gb",
                                          "seconds_per_db_max", "ms_per_question"])
        w.writeheader()
        w.writerows(offline)
    print(open(LAT / "summary.csv").read())
    print(open(LAT / "offline.csv").read())


if __name__ == "__main__":
    main()
