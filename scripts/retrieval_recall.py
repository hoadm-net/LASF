"""
scripts/retrieval_recall.py — Recall of the gold schema elements after top-k filtering (no SQL generation).

For every question, the gold tables and columns are extracted from the gold SQL (sqlglot,
aliases resolved against the database schema). Columns are ranked once per question and
the filtered schema is rebuilt for each k, so all k values share the same ranking.

Usage:
    python scripts/retrieval_recall.py --dataset bird_vi --linkers e5-plain e5-aug
    python scripts/retrieval_recall.py --dataset spider_vi --ks 5 10 20 --ratios 0.25 0.45

Output: evaluation/analysis_v2/recall/{dataset}_per_question.jsonl and {dataset}_summary.csv
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_spider_vi, load_bird_vi, load_schema_from_db, load_augmented_schema, Schema
from linking.schema_linker import SchemaLinker, select_top_k

DEFAULT_KS = [5, 10, 15, 20, 30, 50]
DEFAULT_RATIOS = [0.15, 0.25, 0.45]


def gold_elements(sql: str, schema: Schema) -> tuple[set[str], set[tuple[str, str]]] | None:
    """Gold tables and (table, column) pairs referenced by `sql`, lowercased. None if unparsable."""
    try:
        tree = sqlglot.parse_one(sql, dialect="sqlite")
    except Exception:
        return None
    table_cols = {t.name.lower(): {c.name.lower() for c in t.columns} for t in schema.tables}

    tables, alias_map = set(), {}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name in table_cols:
            tables.add(name)
            alias_map[name] = name
            if t.alias:
                alias_map[t.alias.lower()] = name

    columns = set()
    for c in tree.find_all(exp.Column):
        col = c.name.lower()
        if c.table:
            tbl = alias_map.get(c.table.lower())
            if tbl and col in table_cols[tbl]:
                columns.add((tbl, col))
        else:
            # Unqualified: attribute to every referenced table that has the column
            owners = [t for t in tables if col in table_cols[t]]
            columns.update((t, col) for t in owners)
    return tables, columns


def kept_elements(schema: Schema) -> tuple[set[str], set[tuple[str, str]]]:
    tables = {t.name.lower() for t in schema.tables}
    cols = {(t.name.lower(), c.name.lower()) for t in schema.tables for c in t.columns}
    return tables, cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    ap.add_argument("--lang", choices=["vi", "en"], default="vi")
    ap.add_argument("--linkers", nargs="+", default=["e5-plain", "e5-aug"], choices=["e5-plain", "e5-aug"])
    ap.add_argument("--ks", nargs="+", type=int, default=DEFAULT_KS)
    ap.add_argument("--ratios", nargs="+", type=float, default=DEFAULT_RATIOS)
    ap.add_argument("--cfg", default="configs/config.yaml")
    ap.add_argument("--out", default="evaluation/analysis_v2/recall")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.cfg))
    data_cfg = cfg["data"][args.dataset]
    loader = load_spider_vi if args.dataset == "spider_vi" else load_bird_vi
    examples = loader(data_cfg["dev"], lang=args.lang)

    plain = {}
    for db in sorted({e.db_id for e in examples}):
        plain[db] = load_schema_from_db(str(Path(data_cfg["db_dir"]) / db / f"{db}.sqlite"), db)
    aug = {}
    if "e5-aug" in args.linkers:
        for db in plain:
            aug[db] = load_augmented_schema(cfg["augmentation"]["output_dir"], db)
            if aug[db] is None:
                raise FileNotFoundError(f"No augmented schema for {db}")

    linker = SchemaLinker(model_name=cfg["linking"]["model"], device=cfg["linking"]["device"])
    settings = [("k", k) for k in args.ks] + [("r", r) for r in args.ratios]

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_q_path = out_dir / f"{args.dataset}{'_en' if args.lang == 'en' else ''}_per_question.jsonl"
    agg = defaultdict(lambda: defaultdict(float))
    n_unparsable = 0

    with open(per_q_path, "w", encoding="utf-8") as fout:
        for ex in tqdm(examples, desc="recall"):
            gold = gold_elements(ex.gold_sql, plain[ex.db_id])
            if gold is None or not gold[0]:
                n_unparsable += 1
                continue
            gold_tables, gold_cols = gold
            for linker_name in args.linkers:
                schema = aug[ex.db_id] if linker_name == "e5-aug" else plain[ex.db_id]
                column_index, scores = linker.score_columns(ex.question, schema)
                n_total = len(column_index)
                for kind, val in settings:
                    k = val if kind == "k" else max(1, round(val * n_total))
                    kept_t, kept_c = kept_elements(select_top_k(schema, column_index, scores, k))
                    row = {
                        "question_id": ex.question_id, "db_id": ex.db_id, "difficulty": ex.difficulty,
                        "linker": linker_name, "setting": f"{kind}{val:g}", "k": k,
                        "n_gold_tables": len(gold_tables), "n_gold_cols": len(gold_cols),
                        "table_recall": len(gold_tables & kept_t) / len(gold_tables),
                        "all_tables_kept": int(gold_tables <= kept_t),
                        "col_recall": len(gold_cols & kept_c) / len(gold_cols) if gold_cols else 1.0,
                        "all_cols_kept": int(gold_cols <= kept_c),
                        "kept_col_ratio": len(kept_c) / n_total,
                        "n_cols_kept": len(kept_c), "n_cols_total": n_total,
                    }
                    fout.write(json.dumps(row) + "\n")
                    a = agg[(linker_name, row["setting"])]
                    a["n"] += 1
                    for key in ("table_recall", "all_tables_kept", "col_recall", "all_cols_kept",
                                "kept_col_ratio", "n_cols_kept"):
                        a[key] += row[key]
                    if row["n_gold_tables"] > 1:
                        a["n_multi"] += 1
                        a["all_tables_kept_multi"] += row["all_tables_kept"]

    summary_path = out_dir / f"{args.dataset}{'_en' if args.lang == 'en' else ''}_summary.csv"
    fields = ["linker", "setting", "n", "table_recall", "all_tables_kept", "all_tables_kept_multi",
              "col_recall", "all_cols_kept", "kept_col_ratio", "n_cols_kept"]
    with open(summary_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for (linker_name, setting), a in agg.items():
            n = a["n"]
            w.writerow({
                "linker": linker_name, "setting": setting, "n": int(n),
                "table_recall": round(a["table_recall"] / n, 4),
                "all_tables_kept": round(a["all_tables_kept"] / n, 4),
                "all_tables_kept_multi": round(a["all_tables_kept_multi"] / a["n_multi"], 4) if a["n_multi"] else "",
                "col_recall": round(a["col_recall"] / n, 4),
                "all_cols_kept": round(a["all_cols_kept"] / n, 4),
                "kept_col_ratio": round(a["kept_col_ratio"] / n, 4),
                "n_cols_kept": round(a["n_cols_kept"] / n, 1),
            })
    print(f"Unparsable/no-table gold SQL: {n_unparsable}")
    print(open(summary_path).read())


if __name__ == "__main__":
    main()
