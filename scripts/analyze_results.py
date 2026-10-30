"""
scripts/analyze_results.py — Per-run breakdowns of the v2 results (A1, A2, A5, A6).

  A1  invalid SQL: execution status of every prediction; errors are split by compiling the
      query with EXPLAIN (syntax error / no such table / no such column / other)
  A2  EX by difficulty: Spider hardness (official evaluator) and sql_class; BIRD difficulty
  A5  EX when every gold table survives filtering vs when at least one is dropped
  A6  prompt length and truncation; share of prompts above the v1 limit of 4096 tokens

Usage:
    python scripts/analyze_results.py --dataset spider_vi
    python scripts/analyze_results.py --dataset bird_vi

Output: evaluation/analysis_v2/breakdown/{dataset}_{runs,difficulty,gold_tables}.csv
"""

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_spider_vi, load_bird_vi, load_schema_from_db
from scripts.retrieval_recall import gold_elements

V1_MAX_TOKENS = 4096


def error_category(sql: str, db_path: str) -> str:
    """Compile (not run) the query and classify the error message."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.execute(f"EXPLAIN {sql}")
        return "runtime"
    except sqlite3.Error as e:
        msg = str(e).lower()
        for key, label in (("syntax error", "syntax"), ("incomplete input", "syntax"),
                           ("unrecognized token", "syntax"), ("no such table", "no_table"),
                           ("no such column", "no_column"), ("ambiguous column", "ambiguous_column"),
                           ("no such function", "no_function")):
            if key in msg:
                return label
        return "other"
    except Exception:
        return "other"
    finally:
        conn.close()


def spider_hardness(examples, db_dir: str) -> dict[str, str]:
    """Official Spider hardness (easy/medium/hard/extra) of each gold query."""
    sys.path.insert(0, "third_party/spider")
    from evaluation import Evaluator
    from process_sql import Schema as SpiderSchema, get_schema, get_sql
    evaluator, schemas, out = Evaluator(), {}, {}
    for ex in examples:
        if ex.db_id not in schemas:
            schemas[ex.db_id] = SpiderSchema(get_schema(str(Path(db_dir) / ex.db_id / f"{ex.db_id}.sqlite")))
        try:
            out[ex.question_id] = evaluator.eval_hardness(get_sql(schemas[ex.db_id], ex.gold_sql))
        except Exception:
            out[ex.question_id] = "unparsed"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    ap.add_argument("--results_dir", default="evaluation/results_v2")
    ap.add_argument("--cfg", default="configs/config.yaml")
    ap.add_argument("--out", default="evaluation/analysis_v2/breakdown")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.cfg))
    data_cfg = cfg["data"][args.dataset]
    loader = load_spider_vi if args.dataset == "spider_vi" else load_bird_vi
    examples = loader(data_cfg["dev"], lang="vi")
    db_path = {db: str(Path(data_cfg["db_dir"]) / db / f"{db}.sqlite") for db in {e.db_id for e in examples}}
    schemas = {db: load_schema_from_db(p, db) for db, p in db_path.items()}

    levels = {}  # question_id -> {grouping: level}
    hardness = spider_hardness(examples, data_cfg["db_dir"]) if args.dataset == "spider_vi" else {}
    for ex in examples:
        if args.dataset == "spider_vi":
            levels[ex.question_id] = {"hardness": hardness[ex.question_id], "sql_class": ex.difficulty}
        else:
            levels[ex.question_id] = {"difficulty": ex.difficulty}
    gold_tables = {}
    for ex in examples:
        g = gold_elements(ex.gold_sql, schemas[ex.db_id])
        gold_tables[ex.question_id] = {t for t in g[0]} if g and g[0] else None

    err_cache: dict[tuple[str, str], str] = {}
    run_rows, diff_rows, gold_rows = [], [], []
    for meta_path in sorted(Path(args.results_dir, args.dataset).glob("*.meta.json")):
        meta = json.loads(meta_path.read_text())
        if meta["args"].get("limit") or meta["args"].get("db_filter"):
            continue
        stem = meta_path.name[:-len(".meta.json")]
        with open(meta_path.with_name(stem + ".jsonl"), encoding="utf-8") as f:
            recs = [json.loads(line) for line in f]
        n = len(recs)

        # A1 + A6
        status = defaultdict(int)
        for r in recs:
            s = r["exec_status"]
            if s == "error":
                key = (r["db_id"], r["pred_sql"])
                if key not in err_cache:
                    err_cache[key] = error_category(r["pred_sql"], db_path[r["db_id"]])
                s = "error_" + err_cache[key]
            status[s] += 1
        tokens = np.array([int(r["prompt_tokens"]) for r in recs])
        row = {"run": stem, "n": n, "ex": round(np.mean([int(r["execution_accuracy"]) for r in recs]), 4),
               "invalid_rate": round(1 - status["ok"] / n, 4)}
        for s in ("ok", "empty_sql", "timeout", "error_syntax", "error_no_table", "error_no_column",
                  "error_ambiguous_column", "error_no_function", "error_runtime", "error_other"):
            row[s] = status.get(s, 0)
        row.update({"prompt_tokens_mean": round(tokens.mean(), 1), "prompt_tokens_median": int(np.median(tokens)),
                    "prompt_tokens_p95": int(np.percentile(tokens, 95)), "prompt_tokens_max": int(tokens.max()),
                    "n_over_4096": int((tokens > V1_MAX_TOKENS).sum()),
                    "n_truncated": sum(bool(r.get("truncated")) for r in recs),
                    "gen_ms_mean": round(np.mean([float(r.get("gen_ms") or 0) for r in recs]), 1)})
        run_rows.append(row)

        # A2
        groups = defaultdict(list)
        for r in recs:
            for grouping, level in levels.get(r["question_id"], {}).items():
                groups[(grouping, level)].append(int(r["execution_accuracy"]))
        for (grouping, level), vals in sorted(groups.items()):
            diff_rows.append({"run": stem, "grouping": grouping, "level": level,
                              "n": len(vals), "ex": round(np.mean(vals), 4)})

        # A5 (runs with schema filtering only)
        if not meta.get("use_link"):
            continue
        kept, missing = [], []
        for r in recs:
            gold = gold_tables.get(r["question_id"])
            if not gold or r.get("tables_kept") is None:
                continue
            tk = {t.lower() for t in r["tables_kept"]}
            (kept if gold <= tk else missing).append(int(r["execution_accuracy"]))
        gold_rows.append({"run": stem, "n_all_gold_kept": len(kept),
                          "ex_all_gold_kept": round(np.mean(kept), 4) if kept else "",
                          "n_gold_missing": len(missing),
                          "ex_gold_missing": round(np.mean(missing), 4) if missing else ""})

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("runs", run_rows), ("difficulty", diff_rows), ("gold_tables", gold_rows)):
        if not rows:
            continue
        with open(out / f"{args.dataset}_{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Saved {out / f'{args.dataset}_{name}.csv'}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
