import hashlib
import os
import pickle
import re
import sqlite3
import time
from pathlib import Path

# Gold query results are identical across runs; cache them on disk per database directory
GOLD_CACHE_DIR = Path("evaluation/.gold_cache")

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


def run_sql(sql: str, db_path: str, timeout: float = 30.0) -> tuple[list | None, str]:
    """Execute SQL read-only. Returns (rows, status) with status in {"ok", "error", "timeout", "empty_sql"}."""
    if not sql or not sql.strip():
        return None, "empty_sql"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.text_factory = lambda b: b.decode(errors="ignore")
    # Cancel query if it takes longer than `timeout` seconds
    deadline = time.time() + timeout
    conn.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 100)
    try:
        return conn.execute(sql).fetchall(), "ok"
    except sqlite3.OperationalError as e:
        return None, "timeout" if "interrupted" in str(e) else "error"
    except Exception:
        return None, "error"
    finally:
        conn.close()


def execute_sql(sql: str, db_path: str, timeout: float = 30.0):
    """Execute SQL and return result set, or None on error/timeout."""
    return run_sql(sql, db_path, timeout)[0]


def execution_accuracy(pred_sql: str, gold_sql: str, db_path: str) -> int:
    return execution_check(pred_sql, gold_sql, db_path)[0]


def execution_check(pred_sql: str, gold_sql: str, db_path: str, gold_cache: dict | None = None) -> tuple[int, str, str]:
    """Returns (ex, pred_status, gold_status). EX compares result sets as sets (order and duplicates ignored)."""
    pred_result, pred_status = run_sql(pred_sql, db_path)
    key = (db_path, gold_sql)
    if gold_cache is not None and key in gold_cache:
        gold_result, gold_status = gold_cache[key]
    else:
        gold_result, gold_status = run_sql(gold_sql, db_path)
        if gold_cache is not None:
            gold_cache[key] = (gold_result, gold_status)
    if pred_result is None or gold_result is None:
        return 0, pred_status, gold_status
    return int(set(pred_result) == set(gold_result)), pred_status, gold_status


def compute_metrics(
    predictions: list[dict],
    db_dir: str,
) -> dict:
    """
    predictions: list of dicts with keys:
        question_id, db_id, pred_sql, gold_sql
    Returns dict with em, ex, and per-sample binary lists.
    """
    cache_path = GOLD_CACHE_DIR / (hashlib.sha1(str(Path(db_dir).resolve()).encode()).hexdigest()[:12] + ".pkl")
    gold_cache = {}
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            gold_cache = pickle.load(f)
    n_cached = len(gold_cache)

    em_list, ex_list, pred_status_list, gold_status_list = [], [], [], []
    for item in predictions:
        db_path = str(Path(db_dir) / item["db_id"] / f"{item['db_id']}.sqlite")
        em_list.append(exact_match(item["pred_sql"], item["gold_sql"]))
        ex, pred_status, gold_status = execution_check(item["pred_sql"], item["gold_sql"], db_path, gold_cache)
        ex_list.append(ex)
        pred_status_list.append(pred_status)
        gold_status_list.append(gold_status)

    if len(gold_cache) > n_cached:
        GOLD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(f".{os.getpid()}.tmp")
        with open(tmp, "wb") as f:
            pickle.dump(gold_cache, f)
        os.replace(tmp, cache_path)  # atomic, safe if several runs finish together

    n = len(predictions)
    return {
        "em": sum(em_list) / n,
        "ex": sum(ex_list) / n,
        "em_list": em_list,
        "ex_list": ex_list,
        "pred_status_list": pred_status_list,
        "gold_status_list": gold_status_list,
        "invalid_rate": sum(st != "ok" for st in pred_status_list) / n,
        "n": n,
    }
