import re
import sqlite3
import time
from pathlib import Path

import sqlglot


def normalize_sql(sql: str) -> str:
    """Normalize SQL for exact match comparison."""
    try:
        parsed = sqlglot.parse_one(sql, dialect="sqlite")
        return parsed.sql(dialect="sqlite").lower().strip()
    except Exception:
        # Fallback: basic normalization
        sql = sql.lower().strip()
        sql = re.sub(r"\s+", " ", sql)
        sql = sql.rstrip(";")
        return sql


def exact_match(pred_sql: str, gold_sql: str) -> int:
    return int(normalize_sql(pred_sql) == normalize_sql(gold_sql))


def execute_sql(sql: str, db_path: str, timeout: float = 30.0):
    """Execute SQL and return result set, or None on error/timeout."""
    try:
        conn = sqlite3.connect(db_path)
        conn.text_factory = lambda b: b.decode(errors="ignore")

        # Cancel query if it takes longer than `timeout` seconds
        deadline = time.time() + timeout
        def _progress():
            return 1 if time.time() > deadline else 0
        conn.set_progress_handler(_progress, 100)

        cursor = conn.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        conn.close()
        return result
    except Exception:
        return None


def execution_accuracy(pred_sql: str, gold_sql: str, db_path: str) -> int:
    pred_result = execute_sql(pred_sql, db_path)
    gold_result = execute_sql(gold_sql, db_path)
    if pred_result is None or gold_result is None:
        return 0
    return int(set(pred_result) == set(gold_result))


def compute_metrics(
    predictions: list[dict],
    db_dir: str,
) -> dict:
    """
    predictions: list of dicts with keys:
        question_id, db_id, pred_sql, gold_sql
    Returns dict with em, ex, and per-sample binary lists.
    """
    em_list, ex_list = [], []
    for item in predictions:
        db_path = str(Path(db_dir) / item["db_id"] / f"{item['db_id']}.sqlite")
        em_list.append(exact_match(item["pred_sql"], item["gold_sql"]))
        ex_list.append(execution_accuracy(item["pred_sql"], item["gold_sql"], db_path))

    n = len(predictions)
    return {
        "em": sum(em_list) / n,
        "ex": sum(ex_list) / n,
        "em_list": em_list,
        "ex_list": ex_list,
        "n": n,
    }
