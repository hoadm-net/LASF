"""
run_experiment.py — Entry point for running ablation experiments.

Usage:
    python run_experiment.py --dataset spider_vi --model Qwen/Qwen2.5-Coder-3B-Instruct --config full
    python run_experiment.py --dataset bird_vi --model Qwen/Qwen2.5-Coder-7B-Instruct --config augret --top_k 20
    python run_experiment.py --dataset spider_vi --model gpt-4.1-mini --config baseline
    python run_experiment.py --dataset spider_vi --model Qwen/Qwen2.5-Coder-0.5B-Instruct --config full --limit 20

Configs:
    baseline  full schema, no augmentation
    +aug      full schema, augmentation metadata in the prompt
    +link     filtered schema (retrieval over plain columns), plain prompt
    augret    filtered schema (retrieval over augmented columns), plain prompt
    full      filtered schema (retrieval over augmented columns), augmentation metadata in the prompt
"""

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()  # load .env vào os.environ

from utils.data_loader import load_spider_vi, load_bird_vi, load_schema_from_db, load_augmented_schema
from generation.sql_generator import SQLGenerator, GPT4O_MINI
from linking.schema_linker import SchemaLinker
from evaluation.metrics import compute_metrics

# config -> (aug_retrieval, aug_prompt, use_link)
CONFIGS = {
    "baseline": (False, False, False),
    "+aug": (False, True, False),
    "+link": (False, False, True),
    "augret": (True, False, True),
    "full": (True, True, True),
}
GPT4O_MINI_ALLOWED_CONFIGS = ["baseline", "full"]
DEFAULT_TOP_K = 10


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    parser.add_argument("--model", required=True, help="HuggingFace model name or path")
    parser.add_argument("--config", choices=list(CONFIGS), required=True)
    parser.add_argument("--lang", choices=["vi", "en"], default="vi", help="Question language")
    parser.add_argument("--top_k", type=int, default=None, help="Columns kept by linking (default: config.yaml)")
    parser.add_argument("--top_k_ratio", type=float, default=None, help="Keep this fraction of each DB's columns")
    parser.add_argument("--max_input_tokens", type=int, default=32768, help="Prompt budget; the schema is cut to fit")
    parser.add_argument("--cfg", default="configs/config.yaml", help="Path to config.yaml")
    parser.add_argument("--device", default=None, help="Override device (cpu/cuda)")
    parser.add_argument("--batch-size", type=int, default=8, help="Max examples per batch (local models)")
    parser.add_argument("--max_batch_tokens", type=int, default=32768,
                        help="Max padded prompt tokens per batch (local models)")
    parser.add_argument("--results_dir", default=None, help="Default: evaluation.results_dir_v2 in config.yaml")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N examples (debugging)")
    parser.add_argument("--db_filter", default=None, help="Only questions on this database (debugging)")
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def short_model_name(model_name: str) -> str:
    return model_name.split("/")[-1].lower().replace("-instruct", "")


def result_stem(config: str, model: str, lang: str = "vi", top_k: int | None = None,
                top_k_ratio: float | None = None) -> str:
    """{config}[_k{k}|_r{ratio}][_en]_{model} — k suffix only for non-default linking settings."""
    parts = [config.replace("+", "plus")]
    if CONFIGS[config][2]:
        if top_k_ratio is not None:
            parts.append(f"r{top_k_ratio:g}")
        elif top_k is not None and top_k != DEFAULT_TOP_K:
            parts.append(f"k{top_k}")
    if lang != "vi":
        parts.append(lang)
    return "_".join(parts) + "_" + short_model_name(model)


def make_batches(order: list[int], lengths: list[int], max_size: int, max_tokens: int) -> list[list[int]]:
    """Greedy batches over `order` (longest first) bounded by count and padded token budget."""
    batches, cur, cur_max = [], [], 0
    for i in order:
        new_max = max(cur_max, lengths[i])
        if cur and (len(cur) + 1 > max_size or new_max * (len(cur) + 1) > max_tokens):
            batches.append(cur)
            cur, new_max = [], lengths[i]
        cur.append(i)
        cur_max = new_max
    if cur:
        batches.append(cur)
    return batches


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main():
    args = parse_args()
    cfg = load_config(args.cfg)

    is_openai = args.model == GPT4O_MINI
    if is_openai and args.config not in GPT4O_MINI_ALLOWED_CONFIGS:
        raise ValueError(f"{GPT4O_MINI} is a reference model; allowed configs: {GPT4O_MINI_ALLOWED_CONFIGS}")

    device = None if is_openai else (args.device or cfg["generation"]["device"])
    aug_retrieval, aug_prompt, use_link = CONFIGS[args.config]
    use_aug = aug_retrieval or aug_prompt
    top_k = args.top_k if args.top_k is not None else cfg["linking"]["top_k"]

    # Load examples
    data_cfg = cfg["data"][args.dataset]
    loader = load_spider_vi if args.dataset == "spider_vi" else load_bird_vi
    examples = loader(data_cfg["dev"], lang=args.lang)
    if args.db_filter:
        examples = [e for e in examples if e.db_id == args.db_filter]
    if args.limit:
        examples = examples[: args.limit]
    db_dir = data_cfg["db_dir"]

    # Schemas are per database; load each once
    augmented_dir = cfg["augmentation"]["output_dir"]
    schema_cache = {}

    def get_schema(db_id: str, augmented: bool):
        key = (db_id, augmented)
        if key not in schema_cache:
            if augmented:
                schema = load_augmented_schema(augmented_dir, db_id)
                if schema is None:
                    raise FileNotFoundError(f"No augmented schema for {db_id} in {augmented_dir}")
            else:
                schema = load_schema_from_db(str(Path(db_dir) / db_id / f"{db_id}.sqlite"), db_id)
            schema_cache[key] = schema
        return schema_cache[key]

    # Load models
    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    generator = SQLGenerator(
        model_name=args.model,
        device=device or "cpu",
        max_new_tokens=cfg["generation"]["max_new_tokens"],
        max_input_tokens=args.max_input_tokens,
    )
    linker = SchemaLinker(
        model_name=cfg["linking"]["model"],
        device=device or ("cuda" if torch.cuda.is_available() else "cpu"),
        top_k=top_k,
        top_k_ratio=args.top_k_ratio,
    ) if use_link else None

    # 1) Schema selection + prompt construction
    t0 = time.perf_counter()
    records, prompts = [], []
    for ex in tqdm(examples, desc="prompts"):
        full_schema = get_schema(ex.db_id, augmented=use_aug)
        n_cols_total = sum(len(t.columns) for t in full_schema.tables)
        schema = full_schema
        link_ms = None
        if use_link:
            t_link = time.perf_counter()
            schema = linker.retrieve(ex.question, get_schema(ex.db_id, augmented=aug_retrieval))
            link_ms = (time.perf_counter() - t_link) * 1000
        info = generator.build_prompt(ex.question, schema, augmented=aug_prompt, evidence=ex.evidence)
        prompts.append(info["prompt"])
        records.append({
            "question_id": ex.question_id,
            "db_id": ex.db_id,
            "difficulty": ex.difficulty,
            "question": ex.question,
            "question_lang": args.lang,
            "gold_sql": ex.gold_sql,
            "config": args.config,
            "model": args.model,
            "prompt_tokens": info["prompt_tokens"],
            "truncated": info["truncated"],
            "schema_lines_kept": info["schema_lines_kept"],
            "schema_lines_total": info["schema_lines_total"],
            "n_cols_total": n_cols_total,
            "n_cols_kept": sum(len(t.columns) for t in schema.tables),
            "tables_kept": [t.name for t in schema.tables],
            "link_ms": link_ms,
        })
    prep_seconds = time.perf_counter() - t0
    if linker is not None:  # free the encoder's GPU memory before long-context generation
        del linker
        torch.cuda.empty_cache()

    # 2) Generation, longest prompts first so memory problems show up immediately
    lengths = [r["prompt_tokens"] or 0 for r in records]
    order = sorted(range(len(records)), key=lambda i: -lengths[i])
    if is_openai:
        batches = [order[i : i + 16] for i in range(0, len(order), 16)]
    else:
        batches = make_batches(order, lengths, args.batch_size, args.max_batch_tokens)

    def generate_safe(batch: list[int]) -> list[dict]:
        """Split the batch on CUDA OOM; a single example that still does not fit is recorded as 'oom'."""
        try:
            return generator.generate_batch([prompts[i] for i in batch])
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if len(batch) == 1:
                print(f"\n  [OOM] {records[batch[0]]['question_id']} ({lengths[batch[0]]} tokens)")
                return [{"pred_sql": "", "raw_output": "", "output_tokens": 0, "oom": True}]
            mid = len(batch) // 2
            return generate_safe(batch[:mid]) + generate_safe(batch[mid:])

    t0 = time.perf_counter()
    for batch in tqdm(batches, desc=f"{args.config} | {short_model_name(args.model)}"):
        t_batch = time.perf_counter()
        outs = generate_safe(batch)
        per_ex_ms = (time.perf_counter() - t_batch) * 1000 / len(batch)
        for i, out in zip(batch, outs):
            records[i]["oom"] = bool(out.get("oom"))
            records[i]["pred_sql"] = out["pred_sql"]
            records[i]["raw_output"] = out["raw_output"]
            records[i]["output_tokens"] = out.get("output_tokens")
            records[i]["gen_ms"] = per_ex_ms
            if out.get("prompt_tokens") is not None:
                records[i]["prompt_tokens"] = out["prompt_tokens"]
            if out.get("provider"):
                records[i]["provider"] = out["provider"]
    gen_seconds = time.perf_counter() - t0
    peak_vram = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else None

    # 3) Evaluate
    metrics = compute_metrics(records, db_dir)
    for i, item in enumerate(records):
        item["exact_match"] = metrics["em_list"][i]
        item["execution_accuracy"] = metrics["ex_list"][i]
        item["exec_status"] = metrics["pred_status_list"][i]
        item["gold_exec_status"] = metrics["gold_status_list"][i]

    stem = result_stem(args.config, args.model, args.lang, top_k if use_link else None, args.top_k_ratio)
    print(f"\nResults [{stem}]")
    print(f"  EM: {metrics['em']:.4f}  |  EX: {metrics['ex']:.4f}  |  invalid: {metrics['invalid_rate']:.4f}"
          f"  |  truncated: {sum(r['truncated'] for r in records)}  |  N: {metrics['n']}")

    # 4) Save
    results_dir = args.results_dir or cfg["evaluation"].get("results_dir_v2", "evaluation/results_v2")
    out_dir = Path(results_dir) / args.dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.db_filter:
        stem += f"_db-{args.db_filter}"
    if args.limit:
        stem += f"_limit{args.limit}"
    out_path = out_dir / f"{stem}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    import transformers
    meta = {
        "args": vars(args),
        "aug_retrieval": aug_retrieval,
        "aug_prompt": aug_prompt,
        "use_link": use_link,
        "top_k": top_k if use_link else None,
        "linker_model": cfg["linking"]["model"] if use_link else None,
        "api_model": getattr(generator, "api_model", None),
        "n": metrics["n"],
        "em": metrics["em"],
        "ex": metrics["ex"],
        "invalid_rate": metrics["invalid_rate"],
        "n_truncated": sum(r["truncated"] for r in records),
        "n_oom": sum(r.get("oom", False) for r in records),
        "prep_seconds": round(prep_seconds, 1),
        "gen_seconds": round(gen_seconds, 1),
        "peak_vram_gb": round(peak_vram, 2) if peak_vram is not None else None,
        "git_commit": git_commit(),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else platform.processor(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(out_dir / f"{stem}.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"  Saved → {out_path}")


if __name__ == "__main__":
    main()
