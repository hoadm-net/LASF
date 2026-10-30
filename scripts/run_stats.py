"""
scripts/run_stats.py — Paired significance tests for all v2 results (C9 / A4).

For each dataset and model, every pair of runs inside a comparison family is tested with
McNemar's test on per-question EX; p-values are Holm-adjusted within the family, and a
paired bootstrap 95% CI is reported for ΔEX = EX(a) − EX(b).

Families (per dataset × model):
  ablation   all pairs of baseline, +aug, +link, augret, full (Vietnamese, e5, k=10)
  language   baseline vs full on English questions; Vietnamese vs English for each
  k          each k ≠ 10 vs the same config at k=10, and vs baseline
  linker     BM25 / LLM table selection vs e5 for the same config, vs baseline and full
  values     capped sample values (--max_value_chars) vs uncapped, and vs baseline

Usage:
    python scripts/run_stats.py --dataset spider_vi
    python scripts/run_stats.py --dataset bird_vi --n_boot 10000

Output: evaluation/analysis_v2/stats/{dataset}_pairs.csv
"""

import argparse
import csv
import json
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluation.stats import mcnemar_test, holm, paired_bootstrap_ci

ABLATION = ["baseline", "+aug", "+link", "augret", "full"]
DEFAULT_K = 10


def load_runs(results_dir: Path) -> dict[tuple, dict]:
    """Key: (model, config, lang, k, linker, max_value_chars) → {'ex': {qid: 0/1}, 'stem': str}."""
    runs = {}
    for meta_path in sorted(results_dir.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text())
        a = meta["args"]
        if a.get("limit") or a.get("db_filter") or a.get("sample") or a.get("top_k_ratio"):
            continue
        jsonl = meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl"))
        ex = {}
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                ex[r["question_id"]] = int(r["execution_accuracy"])
        model = a["model"].split("/")[-1].lower().replace("-instruct", "")
        key = (model, a["config"], a.get("lang", "vi"), a.get("top_k") or DEFAULT_K,
               a.get("linker", "e5"), a.get("max_value_chars"))
        runs[key] = {"ex": ex, "stem": jsonl.stem}
    return runs


def families(runs: dict, model: str) -> dict[str, list[tuple]]:
    """Pairs (key_a, key_b) per family for one model, restricted to runs that exist."""
    def k(config, lang="vi", top_k=DEFAULT_K, linker="e5", mvc=None):
        return (model, config, lang, top_k, linker, mvc)

    fam = {"ablation": [], "language": [], "k": [], "linker": [], "values": []}
    present = [c for c in ABLATION if k(c) in runs]
    fam["ablation"] = [(k(b), k(a)) for a, b in combinations(present, 2)]  # later config vs earlier

    fam["language"] = [(k("full", "en"), k("baseline", "en"))]
    fam["language"] += [(k(c, "en"), k(c)) for c in ("baseline", "full")]

    for key in runs:
        m, config, lang, top_k, linker, mvc = key
        if m != model or lang != "vi" or mvc is not None:
            continue
        if top_k != DEFAULT_K and linker == "e5":
            fam["k"] += [(key, k(config)), (key, k("baseline"))]
        if linker != "e5":
            fam["linker"] += [(key, k(config)), (key, k("baseline")), (key, k("full"))]
    for key in runs:
        m, config, lang, top_k, linker, mvc = key
        if m == model and mvc is not None:
            fam["values"] += [(key, k(config)), (key, k("baseline"))]

    return {name: [(a, b) for a, b in pairs if a in runs and b in runs] for name, pairs in fam.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    ap.add_argument("--results_dir", default="evaluation/results_v2")
    ap.add_argument("--n_boot", type=int, default=10_000)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--out", default="evaluation/analysis_v2/stats")
    args = ap.parse_args()

    runs = load_runs(Path(args.results_dir) / args.dataset)
    rows = []
    for model in sorted({key[0] for key in runs}):
        for fam_name, pairs in families(runs, model).items():
            fam_rows = []
            for ka, kb in pairs:
                ea, eb = runs[ka]["ex"], runs[kb]["ex"]
                qids = sorted(ea.keys() & eb.keys())
                la, lb = [ea[q] for q in qids], [eb[q] for q in qids]
                test = mcnemar_test(la, lb)
                lo, hi = paired_bootstrap_ci(la, lb, n_boot=args.n_boot, alpha=args.alpha)
                ex_a, ex_b = sum(la) / len(qids), sum(lb) / len(qids)
                fam_rows.append({
                    "family": fam_name, "model": model, "a": runs[ka]["stem"], "b": runs[kb]["stem"],
                    "n": len(qids), "ex_a": round(ex_a, 4), "ex_b": round(ex_b, 4),
                    "delta": round(ex_a - ex_b, 4), "ci_low": round(lo, 4), "ci_high": round(hi, 4),
                    "a_only": test["a_only"], "b_only": test["b_only"], "test": test["test"],
                    "p": test["p_value"],
                })
            for row, p_adj in zip(fam_rows, holm([r["p"] for r in fam_rows])):
                row["p_holm"] = p_adj
                row["significant"] = int(p_adj < args.alpha)
            rows += fam_rows

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{args.dataset}_pairs.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({**r, "p": f"{r['p']:.3g}", "p_holm": f"{r['p_holm']:.3g}"})

    print(f"Saved {path}  ({len(rows)} comparisons)")
    for r in rows:
        if r["family"] == "ablation" or r["model"] == "gpt-4.1-mini":
            mark = "*" if r["significant"] else " "
            print(f"  {r['model']:20s} {r['a']:40s} vs {r['b']:40s} Δ={100 * r['delta']:+5.1f} "
                  f"[{100 * r['ci_low']:+5.1f}, {100 * r['ci_high']:+5.1f}]  p_holm={r['p_holm']:.3g} {mark}")


if __name__ == "__main__":
    main()
