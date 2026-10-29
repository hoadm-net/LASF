"""
scripts/llm_table_selection.py — Precompute zero-shot LLM table selections (baseline linker, E7).

Usage:
    python scripts/llm_table_selection.py --dataset bird_vi
    python scripts/llm_table_selection.py --dataset spider_vi --lang en

Output: evaluation/analysis_v2/llm_selection/{dataset}[_en].jsonl  (one line per question)
"""

import argparse
import json
import sys
import time
from pathlib import Path

import torch
import yaml
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.data_loader import load_spider_vi, load_bird_vi, load_schema_from_db
from linking.llm_table_selector import build_table_selection_prompt, parse_tables


def cache_path(dataset: str, lang: str = "vi") -> Path:
    return Path("evaluation/analysis_v2/llm_selection") / f"{dataset}{'_en' if lang == 'en' else ''}.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["spider_vi", "bird_vi"], required=True)
    ap.add_argument("--lang", choices=["vi", "en"], default="vi")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--batch_size", type=int, default=8)
    ap.add_argument("--max_batch_tokens", type=int, default=24576)
    ap.add_argument("--cfg", default="configs/config.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.cfg))
    data_cfg = cfg["data"][args.dataset]
    loader = load_spider_vi if args.dataset == "spider_vi" else load_bird_vi
    examples = loader(data_cfg["dev"], lang=args.lang)
    schemas = {db: load_schema_from_db(str(Path(data_cfg["db_dir"]) / db / f"{db}.sqlite"), db)
               for db in sorted({e.db_id for e in examples})}

    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float16, device_map="cuda").eval()

    texts = [tok.apply_chat_template([{"role": "user", "content": build_table_selection_prompt(
        e.question, schemas[e.db_id], e.evidence)}], tokenize=False, add_generation_prompt=True) for e in examples]
    lengths = [len(tok(t)["input_ids"]) for t in texts]
    order = sorted(range(len(texts)), key=lambda i: -lengths[i])

    batches, cur = [], []
    for i in order:
        if cur and (len(cur) >= args.batch_size or lengths[cur[0]] * (len(cur) + 1) > args.max_batch_tokens):
            batches.append(cur)
            cur = []
        cur.append(i)
    if cur:
        batches.append(cur)

    outputs = [None] * len(texts)
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    for batch in tqdm(batches, desc="table selection"):
        enc = tok([texts[i] for i in batch], return_tensors="pt", padding=True).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=128, do_sample=False, pad_token_id=tok.pad_token_id)
        for i, g in zip(batch, gen):
            outputs[i] = tok.decode(g[enc["input_ids"].shape[1]:], skip_special_tokens=True)
    seconds = time.perf_counter() - start

    out = cache_path(args.dataset, args.lang)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for e, raw, n in zip(examples, outputs, lengths):
            f.write(json.dumps({"question_id": e.question_id, "db_id": e.db_id, "question": e.question,
                                "tables": parse_tables(raw, schemas[e.db_id]), "raw": raw,
                                "prompt_tokens": n}, ensure_ascii=False) + "\n")
    meta = {"model": args.model, "n": len(examples), "seconds": round(seconds, 1),
            "ms_per_question": round(1000 * seconds / len(examples), 1),
            "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)}
    json.dump(meta, open(out.with_suffix(".meta.json"), "w"), indent=2)
    print(f"Saved {out}  {meta}")


if __name__ == "__main__":
    main()
