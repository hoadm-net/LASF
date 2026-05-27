"""
run_experiment.py — Entry point for running ablation experiments.

Usage:
    python run_experiment.py --dataset spider_vi --model Qwen/Qwen2.5-Coder-3B-Instruct --config full
    python run_experiment.py --dataset spider_vi --model Qwen/Qwen2.5-Coder-3B-Instruct --config baseline
    python run_experiment.py --dataset spider_vi --model gpt-4o-mini --config baseline
"""

import argparse
import json
from pathlib import Path

import yaml
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()  # load .env vào os.environ

from utils.data_loader import load_spider_vi, load_bird_vi, load_schema_from_db, load_augmented_schema
from generation.sql_generator import SQLGenerator, GPT4O_MINI
from linking.schema_linker import SchemaLinker
from evaluation.metrics import compute_metrics

CONFIGS = ["baseline", "+aug", "+link", "full"]
GPT4O_MINI_ALLOWED_CONFIGS = ["baseline"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    parser.add_argument("--model", required=True, help="HuggingFace model name or path")
    parser.add_argument("--config", choices=CONFIGS, required=True)
    parser.add_argument("--cfg", default="configs/config.yaml", help="Path to config.yaml")
    parser.add_argument("--device", default=None, help="Override device (cpu/cuda)")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for local model generation")
    return parser.parse_args()


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def short_model_name(model_name: str) -> str:
    return model_name.split("/")[-1].lower().replace("-instruct", "")


def main():
    args = parse_args()
    cfg = load_config(args.cfg)

    # GPT-4o-mini is upper-bound reference: only allowed in baseline config
    if args.model == GPT4O_MINI and args.config not in GPT4O_MINI_ALLOWED_CONFIGS:
        raise ValueError(
            f"gpt-4o-mini is an upper-bound reference baseline and only supports config: "
            f"{GPT4O_MINI_ALLOWED_CONFIGS}. Got: '{args.config}'"
        )

    # GPT-4o-mini uses OpenAI API, no device needed
    is_openai = args.model == GPT4O_MINI
    device = None if is_openai else (args.device or cfg["generation"]["device"])
    use_aug = args.config in ["+aug", "full"]
    use_link = args.config in ["+link", "full"]

    # Load examples
    if args.dataset == "spider_vi":
        examples = load_spider_vi(cfg["data"]["spider_vi"]["dev"])
        db_dir = cfg["data"]["spider_vi"]["db_dir"]
    else:
        examples = load_bird_vi(cfg["data"]["bird_vi"]["dev"])
        db_dir = cfg["data"]["bird_vi"]["db_dir"]

    # Load models
    generator = SQLGenerator(model_name=args.model, device=device or "cpu")
    linker = SchemaLinker(
        model_name=cfg["linking"]["model"],
        device=device or "cpu",
        top_k=cfg["linking"]["top_k"],
    ) if use_link else None

    augmented_dir = cfg["augmentation"]["output_dir"]
    predictions = []
    batch_size = 1 if is_openai else args.batch_size

    for batch_start in tqdm(
        range(0, len(examples), batch_size),
        desc=f"{args.config} | {short_model_name(args.model)}",
        total=(len(examples) + batch_size - 1) // batch_size,
    ):
        batch = examples[batch_start : batch_start + batch_size]

        # Prepare schemas for each example in batch
        schemas = []
        for ex in batch:
            db_path = str(Path(db_dir) / ex.db_id / f"{ex.db_id}.sqlite")
            if use_aug:
                schema = load_augmented_schema(augmented_dir, ex.db_id)
                if schema is None:
                    schema = load_schema_from_db(db_path, ex.db_id)
            else:
                schema = load_schema_from_db(db_path, ex.db_id)
            if use_link and linker is not None:
                schema = linker.retrieve(ex.question, schema)
            schemas.append(schema)

        # Batched SQL generation
        pred_sqls = generator.generate_batch(
            [ex.question for ex in batch], schemas, augmented=use_aug
        )

        for ex, schema, pred_sql in zip(batch, schemas, pred_sqls):
            predictions.append({
                "question_id": ex.question_id,
                "db_id": ex.db_id,
                "question": ex.question,
                "gold_sql": ex.gold_sql,
                "pred_sql": pred_sql,
                "config": args.config,
                "model": args.model,
            })

    # Evaluate
    metrics = compute_metrics(predictions, db_dir)
    print(f"\nResults [{args.config}] [{short_model_name(args.model)}]")
    print(f"  EM: {metrics['em']:.4f}  |  EX: {metrics['ex']:.4f}  |  N: {metrics['n']}")

    # Save
    out_dir = Path(cfg["evaluation"]["results_dir"]) / args.dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    model_tag = short_model_name(args.model)
    config_tag = args.config.replace("+", "plus")

    out_path = out_dir / f"{config_tag}_{model_tag}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for item in predictions:
            item["exact_match"] = metrics["em_list"][predictions.index(item)]
            item["execution_accuracy"] = metrics["ex_list"][predictions.index(item)]
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"  Saved → {out_path}")


if __name__ == "__main__":
    main()
