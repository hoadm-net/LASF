"""
scripts/error_categories.py — Automatic error categories for wrong predictions (A3).

Every prediction with EX = 0 gets the first matching category, in this order:
  invalid_sql      prediction does not execute (error / timeout / empty)
  gold_missing     schema filtering dropped a table used by the gold SQL (filtered runs only)
  wrong_tables     set of tables differs from the gold SQL
  wrong_columns    set of referenced columns differs
  wrong_agg_group  aggregate functions or GROUP BY columns differ
  wrong_condition  WHERE/HAVING columns, operators or literal values differ
  wrong_order      ORDER BY / LIMIT differ
  other            same components, different result (DISTINCT, join condition, value format, ...)
Components are compared on lowercased names extracted with sqlglot, so the categories are
indicative; T3 checks a sample by hand.

Usage:
    python scripts/error_categories.py --dataset bird_vi

Output: evaluation/analysis_v2/errors/{dataset}_categories.csv     (counts per run)
        evaluation/analysis_v2/errors/{dataset}_per_question.jsonl (category of every error)
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_spider_vi, load_bird_vi, load_schema_from_db
from scripts.retrieval_recall import gold_elements

CATEGORIES = ["invalid_sql", "gold_missing", "wrong_tables", "wrong_columns", "wrong_agg_group",
              "wrong_condition", "wrong_order", "other"]
AGGS = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)


def components(sql: str) -> dict | None:
    try:
        tree = sqlglot.parse_one(sql, dialect="sqlite")
    except Exception:
        return None
    if tree is None:
        return None

    def cols(node):
        return {c.name.lower() for c in node.find_all(exp.Column)} if node else set()

    def cond(node):
        if node is None:
            return set()
        ops = {type(n).__name__ for n in node.find_all(exp.Binary, exp.In, exp.Between, exp.Like, exp.Not)}
        lits = {str(l.this).lower() for l in node.find_all(exp.Literal)}
        return {("col", c) for c in cols(node)} | {("op", o) for o in ops} | {("lit", l) for l in lits}

    wheres = [s.args.get("where") for s in tree.find_all(exp.Select)]
    havings = [s.args.get("having") for s in tree.find_all(exp.Select)]
    groups = [s.args.get("group") for s in tree.find_all(exp.Select)]
    orders = [s.args.get("order") for s in tree.find_all(exp.Select)]
    limits = [s.args.get("limit") for s in tree.find_all(exp.Select)]
    return {
        "tables": {t.name.lower() for t in tree.find_all(exp.Table)},
        "columns": cols(tree),
        "agg": sorted(type(a).__name__ for a in tree.find_all(*AGGS)),
        "group": set().union(*(cols(g) for g in groups)) if groups else set(),
        "cond": set().union(*(cond(w) for w in wheres + havings)) if wheres or havings else set(),
        "order": sorted(o.sql().lower() for o in orders if o) + sorted(l.sql().lower() for l in limits if l),
    }


def categorize(rec: dict, gold_tables: set | None, gold_comp: dict | None, filtered: bool) -> str:
    if rec["exec_status"] != "ok":
        return "invalid_sql"
    if filtered and gold_tables and not gold_tables <= {t.lower() for t in rec.get("tables_kept") or []}:
        return "gold_missing"
    pred = components(rec["pred_sql"])
    if pred is None or gold_comp is None:
        return "other"
    if pred["tables"] != gold_comp["tables"]:
        return "wrong_tables"
    if pred["columns"] != gold_comp["columns"]:
        return "wrong_columns"
    if pred["agg"] != gold_comp["agg"] or pred["group"] != gold_comp["group"]:
        return "wrong_agg_group"
    if pred["cond"] != gold_comp["cond"]:
        return "wrong_condition"
    if pred["order"] != gold_comp["order"]:
        return "wrong_order"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    ap.add_argument("--results_dir", default="evaluation/results_v2")
    ap.add_argument("--cfg", default="configs/config.yaml")
    ap.add_argument("--out", default="evaluation/analysis_v2/errors")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.cfg))
    data_cfg = cfg["data"][args.dataset]
    loader = load_spider_vi if args.dataset == "spider_vi" else load_bird_vi
    examples = loader(data_cfg["dev"], lang="vi")
    schemas = {db: load_schema_from_db(str(Path(data_cfg["db_dir"]) / db / f"{db}.sqlite"), db)
               for db in {e.db_id for e in examples}}
    gold_tables, gold_comp = {}, {}
    for ex in examples:
        g = gold_elements(ex.gold_sql, schemas[ex.db_id])
        gold_tables[ex.question_id] = g[0] if g else None
        gold_comp[ex.question_id] = components(ex.gold_sql)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(out / f"{args.dataset}_per_question.jsonl", "w", encoding="utf-8") as fq:
        for meta_path in sorted(Path(args.results_dir, args.dataset).glob("*.meta.json")):
            meta = json.loads(meta_path.read_text())
            if meta["args"].get("limit") or meta["args"].get("db_filter"):
                continue
            stem = meta_path.name[:-len(".meta.json")]
            counts, n = Counter(), 0
            with open(meta_path.with_name(stem + ".jsonl"), encoding="utf-8") as f:
                for line in f:
                    r = json.loads(line)
                    n += 1
                    if int(r["execution_accuracy"]):
                        continue
                    qid = r["question_id"]
                    cat = categorize(r, gold_tables.get(qid), gold_comp.get(qid), bool(meta.get("use_link")))
                    counts[cat] += 1
                    fq.write(json.dumps({"run": stem, "question_id": qid, "category": cat}) + "\n")
            n_err = sum(counts.values())
            rows.append({"run": stem, "n": n, "n_errors": n_err,
                         **{c: counts[c] for c in CATEGORIES},
                         **{f"{c}_share": round(counts[c] / n_err, 4) if n_err else "" for c in CATEGORIES}})

    with open(out / f"{args.dataset}_categories.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {out / f'{args.dataset}_categories.csv'}  ({len(rows)} runs)")


if __name__ == "__main__":
    main()
