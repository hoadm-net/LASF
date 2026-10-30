"""
scripts/official_spider_em.py — Official Spider exact-set-match (EM) for every ViSpider run (C7).

Re-implements the per-example loop of third_party/spider/evaluation.py (evaluate(), etype
"match") so EM can be stored per question and broken down by hardness. Predictions that the
Spider parser cannot handle (e.g. column aliases in SELECT) count as wrong, as in the
official script.

Usage:
    python scripts/official_spider_em.py

Output: evaluation/analysis_v2/official_em/spider_vi_runs.csv  (EM overall and per hardness)
        evaluation/analysis_v2/official_em/spider_vi_per_question.jsonl
"""

import argparse
import copy
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, "third_party/spider")
from evaluation import (Evaluator, build_foreign_key_map_from_json, build_valid_col_units,
                        rebuild_sql_col, rebuild_sql_val)
from process_sql import Schema, get_schema, get_sql

LEVELS = ["easy", "medium", "hard", "extra"]
EMPTY_SQL = {"except": None, "from": {"conds": [], "table_units": []}, "groupBy": [], "having": [],
             "intersect": None, "limit": None, "orderBy": [], "select": [False, []], "union": None,
             "where": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", default="evaluation/results_v2/spider_vi")
    ap.add_argument("--cfg", default="configs/config.yaml")
    ap.add_argument("--out", default="evaluation/analysis_v2/official_em")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.cfg))
    db_dir = cfg["data"]["spider_vi"]["db_dir"]
    kmaps = build_foreign_key_map_from_json(str(Path(cfg["data"]["spider_vi"]["dev"]).parent / "tables.json"))
    evaluator, schemas, gold_cache = Evaluator(), {}, {}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(out / "spider_vi_per_question.jsonl", "w") as fq:
        for meta_path in sorted(Path(args.results_dir).glob("*.meta.json")):
            meta = json.loads(meta_path.read_text())
            if meta["args"].get("limit") or meta["args"].get("db_filter"):
                continue
            stem = meta_path.name[:-len(".meta.json")]
            counts, hits, n_unparsed = defaultdict(int), defaultdict(int), 0
            with open(meta_path.with_name(stem + ".jsonl"), encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    db = r["db_id"]
                    if db not in schemas:
                        schemas[db] = Schema(get_schema(str(Path(db_dir) / db / f"{db}.sqlite")))
                    schema = schemas[db]
                    if r["question_id"] not in gold_cache:
                        g_sql = get_sql(schema, r["gold_sql"].strip().rstrip(";"))
                        hardness = evaluator.eval_hardness(g_sql)
                        g_sql = rebuild_sql_col(build_valid_col_units(g_sql["from"]["table_units"], schema),
                                                rebuild_sql_val(g_sql), kmaps[db])
                        gold_cache[r["question_id"]] = (hardness, g_sql)
                    hardness, g_sql = gold_cache[r["question_id"]]
                    g_sql = copy.deepcopy(g_sql)  # eval_sel() and friends remove items from the gold tree
                    try:
                        p_sql = get_sql(schema, (r["pred_sql"] or "").strip().rstrip(";"))
                    except Exception:
                        p_sql, n_unparsed = copy.deepcopy(EMPTY_SQL), n_unparsed + 1
                    try:
                        p_sql = rebuild_sql_col(build_valid_col_units(p_sql["from"]["table_units"], schema),
                                                rebuild_sql_val(p_sql), kmaps[db])
                        em = int(evaluator.eval_exact_match(p_sql, g_sql))
                    except Exception:
                        em = 0
                    counts[hardness] += 1
                    hits[hardness] += em
                    fq.write(json.dumps({"run": stem, "question_id": r["question_id"],
                                         "hardness": hardness, "official_em": em}) + "\n")
            n = sum(counts.values())
            row = {"run": stem, "n": n, "official_em": round(sum(hits.values()) / n, 4),
                   "n_pred_unparsed": n_unparsed}
            for lv in LEVELS:
                row[f"em_{lv}"] = round(hits[lv] / counts[lv], 4) if counts[lv] else ""
                row[f"n_{lv}"] = counts[lv]
            rows.append(row)
            print(f"{stem:40s} EM={100 * row['official_em']:5.1f}  unparsed={n_unparsed}")

    with open(out / "spider_vi_runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {out / 'spider_vi_runs.csv'}")


if __name__ == "__main__":
    main()
