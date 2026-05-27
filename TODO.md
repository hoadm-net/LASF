# LASF — Project TODO

> **LASF**: Lightweight Schema-Aware Framework for Vietnamese Text-to-SQL  
> Target: Q3 Scopus journal

---

## ✅ Setup

- [x] Install dependencies (`requirements.txt`)
- [x] Download Spider-VI dataset (`hoadm/vispider`, 1034 dev examples)
- [x] Download 166 Spider SQLite databases
- [x] Setup Spider official eval scripts (`third_party/spider/`)
- [x] Configure CUDA device (`configs/config.yaml`)
- [x] Create `.env` with `OPENAI_API_KEY`

---

## ✅ Augmentation

- [x] Run offline schema augmentation with Qwen2.5-7B-Instruct
  - Output: `augmentation/augmented_schemas/` — 20/20 Spider-VI DBs ✓

---

## 🔄 Experiments — Spider-VI (in progress)

> Run: `python scripts/run_ablation.py --dataset spider_vi --device cuda`  
> Monitor: `python scripts/progress.py --dataset spider_vi --watch`

### Local models (4 configs × 4 models = 16 experiments)

| Model | baseline | +aug | +link | full |
|---|---|---|---|---|
| Qwen2.5-Coder-0.5B | ✅ | ✅ | ✅ | ✅ |
| Qwen2.5-Coder-1.5B | ✅ | ✅ | ✅ | ✅ |
| Qwen2.5-Coder-3B   | ✅ | ✅ | ✅ | ✅ |
| Qwen2.5-Coder-7B   | ✅ | ✅ | ✅ | ✅ |

### Reference baseline (upper-bound)

| Model | baseline |
|---|---|
| gpt-4.1-mini | ✅ |

---

## ⬜ Experiments — BIRD-VI

- [ ] Download BIRD-VI dataset (`hoadm/vibird`)
- [ ] Run schema augmentation for BIRD-VI DBs
- [ ] Run full ablation on BIRD-VI (same 17 experiments)

---

## ⬜ Evaluation & Analysis

- [x] Show results table: `python scripts/show_results.py --dataset spider_vi`
- [x] Run statistical tests: `python scripts/run_stats.py --dataset spider_vi`
  - H1: McNemar — `full` significantly improves ≤3B (p<0.0001); not significant for 7B
  - H2: McNemar — `+link` only significant for 0.5B (p=0.0004)
  - H3: Spearman ρ=−1.000, p<0.0001 ✅ fully supported
- [x] Results saved to `docs/results_spider_vi.md`
- [ ] Compare results across Spider-VI vs BIRD-VI

---

## ⬜ Paper

- [ ] Write results section (tables, significance markers)
- [ ] Write ablation analysis (H1/H2/H3)
- [ ] Write related work
- [ ] Proofread & submit

---

## Notes

- Batch sizes (RTX 3090, 24GB): 0.5B→32, 1.5B→16, 3B→8, 7B→4
- Augmentation: one-time offline, resume-friendly (`--overwrite` to redo)
- Results saved to `evaluation/results/{dataset}/{config}_{model}.jsonl`
- `gpt-4.1-mini` is upper-bound reference only — runs `baseline` config only
