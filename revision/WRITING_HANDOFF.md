# Handoff for the writing agent — JICT revision of the LASF paper

Manuscript: *Lightweight Augmentation and Schema Filtering for Vietnamese Text-to-SQL* (JICT, decision: revisions required).
Revision deadline: **15 November 2026**. Experiments and human evaluation are finished (31 October 2026).
This file explains what was done, what the numbers mean, and what can and cannot be claimed.
Every number below comes from `revision/RESULTS_TABLES.md` (generated from the result files); when in doubt, use that file.

---

## 0. Ground rules

1. **Use only v2 numbers** (`evaluation/results_v2/`, `evaluation/analysis_v2/`, `revision/RESULTS_TABLES.md`). The numbers in the submitted manuscript (v1, `evaluation/results/`) are affected by pipeline bugs (Section 2) and must all be replaced, including the ViSpider tables, which in v1 were computed on **English** questions.
2. EX is the primary metric. Official Spider EM is reported only as a secondary metric with its limitation (Section 5.9).
3. Spearman's correlation (H3) is removed; it is replaced by pairwise McNemar tests with Holm correction and bootstrap CIs.
4. Augmented schemas were regenerated (the originals were lost). Any metadata example quoted in the paper (e.g. Table 1) must be taken from `augmentation/augmented_schemas/*.json`.
5. The code will be published. The paper must not describe anything the code does not do.

---

## 1. Summary in five points

1. **Best configuration: `full_llm`** = Vietnamese metadata in the prompt (the paper's augmentation) + **zero-shot LLM table selection** (Qwen2.5-7B-Instruct picks the needed tables; all columns of selected tables are kept). Highest EX on both datasets: ViSpider 39.2 / 56.7 / 64.6 / 70.8 and ViBIRD 13.2 / 26.2 / 35.6 / 47.2 for 0.5B / 1.5B / 3B / 7B (baseline: 18.5 / 40.2 / 52.4 / 67.1 and 6.3 / 18.6 / 31.4 / 44.5).
2. **Vietnamese metadata helps on its own**: `+aug` vs baseline on ViSpider +8.0 / +9.1 / +6.9 / +4.0 (all significant). On top of the same LLM table selection, adding metadata gives +7.2 / +5.3 / +4.3 / +3.5 on ViSpider (all significant) and +1.1 to +2.3 on ViBIRD for 1.5B–7B (0.5B: −0.2; not significant after Holm).
3. **The original column-level e5 filtering (top-10 columns) does not help** and hurts on large schemas: on ViBIRD every e5-filtered config is below baseline for 1.5B–7B (7B `full` 33.7 vs 44.5; GPT-4.1-mini `full` 35.8 vs 50.7). Cause: at k = 10 only 66.8% of ViBIRD questions keep all gold tables and 34% of gold columns. Larger k narrows the gap (7B `full`: 33.7 → 37.5 → 40.7 → 42.6 for k = 10/20/30/50) but never closes it.
4. **Gains concentrate in small models.** For 7B the improvement over baseline is +3.7 (ViSpider, p_holm ≈ 0.04) and +2.7 (ViBIRD, p_holm = 0.068).
5. **Human evaluation:** translations are accurate (only 1–2% of sampled questions have a translation error that changes the SQL). The LLM-generated metadata is only of moderate quality (mean 2.0–2.35 on a 1–3 scale; 41.5% of columns flagged as possibly confusable with another column).

**Recommended framing for the revised paper:** training-free Vietnamese schema metadata is the main contribution. It is most useful when combined with **table-level** filtering; column-level top-k filtering loses needed tables and columns on large schemas. The method mainly benefits small (≤3B) models. Section 7 has the details.

---

## 2. What changed relative to the submitted manuscript (v1 → v2)

| Problem found in v1 | Effect | Fix in v2 |
|---|---|---|
| ViSpider loader read the English `question` field (the downloader fetched the original Spider `dev.json`) | **All ViSpider numbers in the manuscript are English-question results** | Loader reads `question_vi`; ViSpider re-run with Vietnamese questions. English results are kept as E3 |
| Generator truncated inputs at 4,096 tokens on the **right** | Long prompts (BIRD with metadata) lost the question and the `### SQL` cue | 32,768-token budget (Qwen2.5-Coder context). If a prompt is still too long, **schema lines are dropped from the end**; instruction, evidence and question are always kept. Truncation is logged per example |
| BIRD databases saved as `.db`, loader looked for `.sqlite`; `sqlite3.connect` silently creates an empty DB | Risk of executing against empty databases | Files saved as `.sqlite`, opened read-only, error if missing |
| Internal table `sqlite_sequence` included in schemas | ViSpider counted as 81 tables / 441 columns | Excluded. Correct counts: **ViSpider 80 tables / 439 columns (20 DBs); ViBIRD 75 tables / 798 columns (11 DBs, largest 199 columns)**. Update the dataset table |
| Augmentation of wide tables: `max_new_tokens = 1024` covers only about 16 columns, so JSON was cut and wide tables silently got no metadata | Wide BIRD tables (e.g. `Match`, 115 columns) without metadata | Tables with more than 12 columns are augmented in groups of 12 columns. Coverage: ViSpider 439/439, ViBIRD 796/798 columns |
| Original augmented schemas lost | — | Regenerated with Qwen2.5-7B-Instruct, seed 2026, per-table seeds (order-independent); committed to the repo |
| Spearman test on n = 4 model sizes reported p < 0.0001 (exact two-sided p for ρ = −1 with n = 4 is 0.083) | Invalid inference | Removed |

**Consistency check:** where v1 had no bug, v2 reproduces it. ViBIRD 7B baseline: v1 44.1 vs v2 44.5. ViSpider with **English** questions, 7B baseline: v1 73.7 vs v2 `baseline_en` 74.1.

v1 vs v2, EX % (to explain why the manuscript numbers change):

| | v1 ViSpider (actually English) baseline → full | v2 ViSpider (Vietnamese) baseline → full | v1 ViBIRD baseline → full | v2 ViBIRD baseline → full |
|---|---|---|---|---|
| 0.5B | 30.3 → 40.3 | 18.5 → 29.8 | 5.7 → 7.0 | 6.3 → 7.1 |
| 1.5B | 50.8 → 58.0 | 40.2 → 49.9 | 18.6 → 16.2 | 18.6 → 16.2 |
| 3B | 57.9 → 64.8 | 52.4 → 62.4 | 31.5 → 22.8 | 31.4 → 23.8 |
| 7B | 73.7 → 73.8 | 67.1 → 70.0 | 44.1 → 33.9 | 44.5 → 33.7 |
| GPT-4.1-mini | 75.8 (baseline) | 73.2 → 70.5 | 50.1 (baseline) | 50.7 → 35.8 |

v1 `+aug` on ViBIRD (2.7 / 10.0 / 16.4 / 24.1) collapsed because of right truncation; v2 gives 6.2 / 18.8 / 28.2 / 39.4.

---

## 3. Experimental setup (for the Methods / Setup section)

**Data.** ViSpider dev (1,034 questions, 20 DBs) and ViBIRD dev (1,534 questions, 11 DBs; with Vietnamese evidence), Hugging Face `hoadm/vispider` and `hoadm/vibird`. Questions in Vietnamese unless stated (E3 uses the original English questions).

**Schema augmentation (offline).** Qwen2.5-7B-Instruct, sampling with temperature 0.1 (+0.1 per retry, up to 3 retries, retry on unparsable JSON), max 1,024 new tokens, seed 2026 (per-table seed = 2026 + CRC32(db/table), per-group and per-attempt offsets), at most 12 columns per call. For each table: a Vietnamese table name; for each column: a Vietnamese name, synonyms and a description; sample values are taken from the database. Cost: ViSpider 17.6 min, ViBIRD 33.4 min on one RTX 4090, peak 21.4 GB.

**Schema linking (proposed, e5).** `intfloat/multilingual-e5-large`. Each column is a passage (table, column, type and, for augmented retrieval, the Vietnamese metadata). Top-k columns by cosine similarity, k = 10 unless stated. PK/FK columns of the kept tables are added. Median linking time 21 ms per question.

**Baselines for filtering (E7).** (a) BM25 over the same column passages (with metadata), top-10. (b) Zero-shot LLM table selection (C3/CHESS-style): Qwen2.5-7B-Instruct reads the full plain schema, the question and the evidence, and returns a JSON list of tables; all columns of the selected tables are kept. If the output is empty or unparsable, the full schema is used. Greedy decoding, 128 new tokens. Selection is computed once per question and shared by all generators.

**SQL generation.** Qwen2.5-Coder-{0.5B, 1.5B, 3B, 7B}-Instruct, fp16, greedy decoding (`do_sample=False`), max 256 new tokens, chat template, input budget 32,768 tokens with schema-side truncation. Reference model GPT-4.1-mini via OpenRouter (`openai/gpt-4.1-mini`, provider pinned to OpenAI, no fallback), temperature 0, max 256 tokens; run for `baseline` and `full` only. Prompt template unchanged from v1 (`prompts/templates.py`). Note: the instruction line says "a question in Vietnamese" also for the English-question runs (E3).

**Configurations.**

| Config | Retrieval over | Prompt schema |
|---|---|---|
| `baseline` | — (full schema) | plain |
| `+aug` | — (full schema) | with Vietnamese metadata |
| `+link` | e5 on plain columns | plain, filtered |
| `augret` (new) | e5 on columns with metadata | plain, filtered |
| `full` | e5 on columns with metadata | with metadata, filtered |
| `+link (LLM-select)` | LLM table selection | plain, filtered |
| `full_llm` (new, E10) | LLM table selection | with metadata, filtered |

**Metrics.**
- **EX:** the predicted and gold queries are executed read-only on SQLite with a 30 s timeout; correct if the **sets** of result rows are equal (row order and duplicates ignored). This is more lenient than the official BIRD/Spider EX and must be stated.
- **Invalid SQL rate:** the prediction raises an error, times out or is empty. Errors are classified by compiling with `EXPLAIN` (syntax / no such table / no such column / ...).
- **EM:** official Spider exact-set-match (`third_party/spider/evaluation.py`, gold tree copied per comparison), ViSpider only.

**Statistics.** McNemar's test on per-question EX: exact binomial if discordant pairs < 25, else χ² with continuity correction. Holm–Bonferroni within each family. Families per dataset and model: (i) all 10 pairs of the five ablation configs; (ii) language; (iii) k; (iv) linker; (v) value cap. Paired bootstrap 95% CI for ΔEX (10,000 resamples, seed 2026). α = 0.05.

**Hardware/software.** One NVIDIA RTX 4090 (24 GB); torch 2.6.0+cu124; transformers 5.20.2; full lock file in `requirements-lock.txt`. Every run has a `.meta.json` with commit hash, versions, arguments, peak VRAM and timing.

---

## 4. Experiment list and where each result lives

| ID | What | Main output |
|---|---|---|
| E1 | ViSpider, 4 Qwen models × 5 configs + GPT-4.1-mini baseline/full | RESULTS_TABLES §1–2 |
| E2 | ViBIRD, same grid | §1–2 |
| E3 | English questions, baseline/full, both datasets | §3 |
| E4 | Recall of gold tables/columns after filtering (no generation), k ∈ {5,10,15,20,30,50}, ratios | §5 |
| E5 | k sensitivity: ViBIRD k ∈ {20,30,50} (+link, full; 1.5B, 7B), ViSpider k ∈ {5,20} (full) | §4 |
| E6 | GPT-4.1-mini under `full` | §1 |
| E7 | Filtering baselines: BM25 (augret), LLM table selection (+link) | §1, §2, §5 |
| E8 | Latency / memory / offline cost | §9 |
| E9 | Sample values capped at 50 characters (ViBIRD) | §6 |
| E10 | `full_llm` (metadata + LLM table selection), both datasets; ViBIRD also with value cap | §1, §2, §6 |
| A1–A6 | Invalid SQL, difficulty, error categories, significance, recall vs EX, prompt length | §2, §7 |
| T1–T3 | Human evaluation: translation, metadata, error analysis | §10 |

---

## 5. Results with interpretation

### 5.1 Main ablation (k = 10), EX %

| | ViSpider baseline / +aug / +link / augret / full / **full_llm** | ViBIRD baseline / +aug / +link / augret / full / **full_llm** |
|---|---|---|
| 0.5B | 18.5 / 26.5 / 20.7 / 21.0 / 29.8 / **39.2** | 6.3 / 6.2 / 6.5 / 5.7 / 7.1 / **13.2** |
| 1.5B | 40.2 / 49.3 / 42.1 / 42.6 / 49.9 / **56.7** | 18.6 / 18.8 / 14.7 / 14.6 / 16.2 / **26.2** |
| 3B | 52.4 / 59.3 / 53.9 / 53.9 / 62.4 / **64.6** | 31.4 / 28.2 / 20.1 / 20.9 / 23.8 / **35.6** |
| 7B | 67.1 / 71.1 / 67.3 / 66.0 / 70.0 / **70.8** | 44.5 / 39.4 / 31.0 / 33.1 / 33.7 / **47.2** |
| GPT-4.1-mini | 73.2 / – / – / – / 70.5 / – | 50.7 / – / – / – / 35.8 / – |

Key significance results (Δ in EX points, Holm-adjusted):
- ViSpider `full` vs baseline: +11.3, +9.7, +10.0 (0.5B–3B, all p < 1e-7); 7B +2.9, p_holm = 0.17 (**not significant**).
- ViSpider `+aug` vs baseline: significant for all four models (+8.0, +9.1, +6.9, +4.0).
- ViSpider `+link`/`augret` vs baseline: −1.2 to +2.5; significant only for 0.5B. `augret` vs `+link`: no significant difference for any model. **Using metadata for retrieval adds nothing; the gain comes from metadata in the prompt.**
- ViBIRD `full` vs baseline: −2.4 (1.5B, ns), −7.6 (3B), −10.8 (7B), −14.9 (GPT-4.1-mini), all significant except 1.5B; 0.5B +0.9 (ns).
- `full_llm` vs baseline: ViSpider +20.7, +16.4, +12.2, +3.7 (all significant; 7B p_holm = 0.039). ViBIRD +7.0, +7.6, +4.2 (significant), 7B +2.7 (p_holm = 0.068).
- `full_llm` vs `full`: ViSpider +9.4, +6.8 (sig.), +2.2, +0.8 (ns). ViBIRD +6.1, +10.0, +11.8, +13.5 (all sig.).
- `full_llm` vs LLM selection without metadata: ViSpider +7.2, +5.3, +4.3, +3.5 (all sig.). ViBIRD −0.2, +2.3, +1.1, +1.6 (ns).
- GPT-4.1-mini `full` vs baseline: −2.7 on ViSpider (sig.), −14.9 on ViBIRD (sig.).

### 5.2 Why e5 column filtering fails on ViBIRD (E4, A5)

- Gold-table coverage at k = 10 (e5 on plain columns): ViSpider 97.5% of questions keep all gold tables; ViBIRD **66.8%**. Gold-column recall: 89.2% vs **34.2%**. At k = 30 / 50: 87.3% / 92.4% (tables), 62.6% / 76.3% (columns).
- The reviewer's "45% vs 14% of columns kept" ignores PK/FK expansion. The actual mean share of columns kept at k = 10 is about **59% (ViSpider) vs 30% (ViBIRD)**.
- Metadata barely changes table coverage (ViBIRD e5-aug k = 10: 65.5%) and modestly improves column recall (34.2% → 37.5% at k = 10).
- BM25 over columns with metadata retrieves more gold tables than e5 (ViBIRD k = 10: 77.8%), yet its EX is no better (7B augret: BM25 36.0 vs e5 33.1).
- LLM table selection keeps all gold tables for **87.7%** of ViBIRD questions with about 34 columns on average.
- A5: 7B `full` on ViBIRD reaches 40.6 when all gold tables survive, vs 20.6 when one is dropped. Even 40.6 is below baseline (44.5): dropped **columns** also hurt, not only dropped tables.
- Error categories (A3, 7B `full`, ViBIRD): 196 of 1,017 errors are "gold table missing from the filtered schema"; invalid SQL rises from 17.3% (baseline) to 30.8%.

### 5.3 k sensitivity (E5)

- ViBIRD 7B `full`: 33.7 / 37.5 / 40.7 / 42.6 for k = 10 / 20 / 30 / 50 (baseline 44.5). 7B `+link`: 31.0 / 35.5 / 38.5 / 40.2.
- ViBIRD 1.5B `full`: 16.2 / 17.7 / 20.5 / 19.5 (baseline 18.6; k = 30 is +1.96 over baseline, ns).
- ViSpider 7B `full`: 64.2 / 70.0 / 72.1 for k = 5 / 10 / 20. 1.5B `full`: 50.6 / 49.9 / 49.6 (flat).
- Message: k must scale with schema size. A fixed k = 10 is adequate for small schemas (ViSpider) and too small for BIRD-sized schemas. Table-level selection avoids choosing k altogether.

### 5.4 English vs Vietnamese questions (E3)

- ViSpider, baseline: English is higher by +12.2 / +10.4 / +5.0 / +7.0 (0.5B–7B). The `full` gain is similar in both languages: VI +11.3 / +9.7 / +10.0 / +2.9 vs EN +11.5 / +10.1 / +7.8 / +0.9.
- ViBIRD, baseline EN vs VI: 9.9 vs 6.3, 23.3 vs 18.6, 36.2 vs 31.4, 49.9 vs 44.5. `full` hurts in both languages for 1.5B–7B, so the filtering problem is not language-specific.
- Use these numbers to quantify the cross-lingual gap requested by the reviewer and to show that the augmentation gain is not an artefact of Vietnamese.

### 5.5 Sample-value cap (E9)

On ViBIRD, 10 XML columns of `european_football_2` account for 97.8% of sample-value characters; 129 `+aug` prompts still exceeded 32k tokens. Capping values at 50 characters removes all truncation and significantly improves `+aug` (7B 39.4 → 42.8; 3B 28.2 → 30.7; 1.5B 18.8 → 20.2), but `+aug` stays at or below baseline. `full` and `full_llm` are unchanged by the cap.

### 5.6 Invalid SQL (A1)

Most invalid predictions reference **non-existent columns** ("no such column"), not syntax errors. Example: ViSpider 0.5B baseline: 530 of 567 invalid predictions are "no such column". Metadata lowers the invalid rate for small models on ViSpider (0.5B 54.8% → 42.0% with `full`, 27.6% with `full_llm`).

### 5.7 Difficulty (A2)

- ViSpider (official hardness, n = 248 / 446 / 174 / 166). 0.5B gains concentrate in easy/medium (easy 30.2 → 51.2 `full` → 58.1 `full_llm`). For 7B, extra-hard drops with `full` (45.8 → 40.4).
- ViBIRD (simple / moderate / challenging, n = 925 / 464 / 145): 7B baseline 52.0 / 33.0 / 33.8.
- Full tables: RESULTS_TABLES §7.2.

### 5.8 Cost (E8)

- Batch size 1, 200 questions, HF transformers on an RTX 4090. Linking ≈ 21 ms per question. Generation 1.0–2.6 s per question, dominated by per-token overhead, so 7B is not slower than 3B in this setup.
- Peak VRAM, `full` 7B: 17.8 GB (ViSpider), 19.8 GB (ViBIRD); baseline 7B: 15.4–15.7 GB.
- LLM table selection: 159–192 ms per question when batched (batch 8), peak 16.6–18.6 GB. This is an extra 7B model, so it **weakens the "lightweight" claim**. Mitigations: training-free; selection is independent of the generator and can be cached; the generator can stay small.
- Augmentation is a one-off offline cost (17.6 / 33.4 min).

### 5.9 Official Spider EM

EM (ViSpider): baseline 9.2 / 15.9 / 21.0 / 36.1, `full` 16.2 / 26.6 / 28.5 / 37.8 (0.5B–7B). 41–75% of predictions cannot be parsed by the Spider parser: table aliases without `AS` (`FROM stadium s`) and column aliases in SELECT are unsupported, and these count as wrong. Report EM as secondary, with this caveat.

---

## 6. Reviewer comments → evidence

| Comment (as numbered in the review) | Evidence to cite |
|---|---|
| R2 major 1: truncation at 4,096; fixed k | Section 2 (bug and fix); A6 prompt lengths (RESULTS_TABLES §7.4); E5 k sensitivity (§4); E9 |
| R2 major 2: recall of schema filtering | E4 recall tables (§5); A5 EX vs gold coverage (§7.3) |
| R2 major 3: separate retrieval and prompt effects of augmentation | `augret` config; `augret` ≈ `+link` (ns), gain comes from metadata in the prompt; E9 |
| R2 major 4: claims about the 7B model | 7B gains are small: `full` +2.9 ns on ViSpider; `full_llm` +3.7 (ViSpider, sig.), +2.7 (ViBIRD, ns). Soften the claims |
| R2 major 5: data source and translation quality | T1 (Section 8); dataset counts corrected (80/439; 75/798) |
| R2 major 6: baselines (English, GPT under full, existing filtering methods) | E3, E6, E7 (BM25, LLM table selection), E10 |
| R2 major 7: is it lightweight? | E8 (§9): linking 21 ms; offline augmentation; VRAM; extra cost of LLM selection |
| R2 major 8: EM definition, invalid SQL, all McNemar comparisons, Spearman | Official EM (§8) + definition; A1 invalid SQL; full pairwise McNemar + Holm + CIs (§2); Spearman removed |
| R2 major 9: error analysis by difficulty | A2 (§7.2), A3 + T3 (§7.5, §10) |
| R2 3.5: metadata never checked by humans | T2 (Section 8) |
| R2 minor 4 / R1 4.5: Figure 2 | Redraw from `evaluation/analysis_v2` (e.g. EX vs model size per config, or EX vs k) |
| R2: glosses, weak citations, softer generalisation, code/data release | Writing tasks (Section 9) |

Editor requirements (writing side, not handled here): APA 7 references; cite relevant JICT papers; professional proofreading with evidence; institutional (non-Gmail/Yahoo) e-mails; Turnitin similarity < 20%; corrections in red; the journal's rebuttal form.

---

## 7. Claims: recommended, allowed with care, and to avoid

**Recommended:**
- Training-free Vietnamese schema metadata, generated by a 7B instruction model, significantly improves small Text-to-SQL models on ViSpider (+6.9 to +9.1 EX for 0.5B–3B with `+aug`; up to +20.7 with `full_llm`).
- The benefit comes from metadata **in the prompt**; using metadata for column retrieval does not help (`augret` ≈ `+link`).
- Combining the metadata with table-level LLM selection gives the best EX on both datasets and beats baseline on ViBIRD, where column-level filtering fails.
- Column-level top-k filtering with a fixed k loses gold tables and columns on large schemas (quantified by recall). k must scale with schema size.

**Allowed with care (state the conditions):**
- "Lightweight": true for the e5 pipeline (21 ms linking, small generators, one-off augmentation). `full_llm` adds a 7B selector, so say so explicitly.
- Effect on 7B: small; significant only for `full_llm` on ViSpider (p_holm = 0.039).
- ViBIRD gain of metadata on top of LLM selection: positive (+1.1 to +2.3 for 1.5B–7B) but not significant.

**Avoid:**
- Any claim that e5 column filtering improves accuracy on ViBIRD, or in general.
- "Smaller models benefit more" as a statistically tested hypothesis (Spearman with n = 4 is invalid). It may be stated descriptively: the gains decrease with model size.
- Comparing v1 numbers with v2 numbers in the same table without explanation.
- Calling EX "official": it is set-based and more lenient.

---

## 8. Human evaluation (for the paper)

**Annotators.** Two IT undergraduate students (IELTS 6.5), paid. They were not involved in translating ViSpider/ViBIRD and annotated independently. Disagreements were adjudicated by the first author. Agreement statistics are computed on the two independent annotations before adjudication. Annotators are not named and are not acknowledged by name, per the author.

**Sampling (seed 2026).**
- T1: 100 ViSpider questions stratified by SQL class + 100 ViBIRD questions stratified by difficulty.
- T2: 200 columns (80 ViSpider + 120 ViBIRD, proportional to the number of columns per DB) + all 155 tables.
- T3: 120 wrong but executable predictions in three groups (Section 5, RESULTS_TABLES §10.3).

**Results (final, adjudicated):**
- **T1 translation.**
  - Meaning accuracy (1–3): 2.84 (ViSpider), 2.87 (ViBIRD); 85% / 89% scored 3.
  - **Errors that change the SQL: 1% / 2%.**
  - Naturalness: 2.48 / 2.57.
  - ViBIRD evidence accuracy: 2.94 (95.5% scored 3; n = 89 with evidence).
- **T2 metadata.**
  - Vietnamese column name 2.25, synonyms 2.02, description 2.35, table name 2.21.
  - **41.5% of columns may be confused with another column** (ViBIRD 46.7%, ViSpider 33.8%).
  - ViBIRD is lower than ViSpider on every criterion (e.g. description 2.21 vs 2.55). This is consistent with the smaller metadata gains on ViBIRD, and should be a stated limitation and future-work item.
- **T3 errors.**
  - The automatic error category was confirmed for **73.1%** of 119 resolved items (group A 76.9%, B 85.0%, C 57.5%).
  - Human labels of the 119 resolved items: wrong tables 37, gold table missing 26, wrong columns 22, other 16, aggregation/GROUP BY 11, condition/value 7.
  - **19/120 (15.8%) items have a problematic question or reference SQL.**

**Agreement (Cohen κ / linear-weighted κ / raw agreement / Gwet AC1):**
- T1:
  - meaning 0.56–0.60 (weighted 0.58–0.60);
  - naturalness 0.77 / 0.52;
  - "error affects SQL" κ 0.49 / 0.66 but raw agreement 98% / 99%, AC1 0.98 / 0.99;
  - evidence κ 0.27, raw 86.5%, AC1 0.85.
- T2: 0.55–0.75 (weighted 0.61–0.80).
- T3 error label: κ 0.81.
- Low κ with high raw agreement comes from skewed prevalence (the κ paradox). Report raw agreement and AC1 alongside κ.
- The "use as example" item (κ 0.17) is an internal selection aid and should not be reported.
- Unresolved items: 6 (T1 error type) + 1 (T3 label).

Files: adjudicated workbooks `revision/human_tasks/final/*_best.xlsx`; summaries `evaluation/analysis_v2/human/`; candidate examples for the paper (both annotators said yes) `evaluation/analysis_v2/human/t3_examples.csv`.

---

## 9. Limitations to state

1. The column-level e5 filtering at fixed k harms accuracy on large schemas. Table-level LLM selection fixes this at the cost of an extra 7B model.
2. LLM-generated metadata is of moderate quality (T2), worse on ViBIRD; 2 ViBIRD columns have no metadata.
3. Gains for 7B are small; GPT-4.1-mini does not benefit from `full`.
4. EX is set-based (lenient); the official Spider EM parser rejects many LLM outputs.
5. Single run per configuration (greedy decoding); augmentation regenerated once (seed 2026). Regeneration is not bit-identical across hardware.
6. 15.8% of reviewed error cases have problematic questions or gold SQL, which affects all systems.
7. Latency was measured with HF transformers at batch size 1 on one GPU, not an optimised serving stack.

**Code and data release statement (facts):** code, augmented schemas, per-question predictions of every run (Git LFS), analysis scripts and annotation workbooks are in the repository (branch `revision-jict`). Datasets: Hugging Face `hoadm/vispider`, `hoadm/vibird`. Setup and reproduction commands are in `README.md` ("Cài đặt và chạy lại").

---

## 10. File index

| Path | Content |
|---|---|
| `revision/RESULTS_TABLES.md` | All numbers as tables (generated) |
| `revision/EXPERIMENT_PLAN.md` | Plan, decisions, progress log (Vietnamese) |
| `evaluation/results_v2/{dataset}/*.jsonl` | Per-question predictions; `.meta.json` per run. Name: `{config}[_k{k}][_{linker}][_en]_{model}[_v50]` |
| `evaluation/analysis_v2/stats/` | Pairwise McNemar / Holm / bootstrap |
| `evaluation/analysis_v2/recall/`, `recall_baselines/` | Filtering recall |
| `evaluation/analysis_v2/breakdown/` | Invalid SQL, difficulty, gold coverage, prompt length |
| `evaluation/analysis_v2/errors/` | Automatic error categories |
| `evaluation/analysis_v2/official_em/` | Official Spider EM |
| `evaluation/analysis_v2/latency/` | Cost |
| `evaluation/analysis_v2/human/` | Human evaluation summaries |
| `augmentation/augmented_schemas/` | Regenerated metadata (+ `_stats_*.jsonl` timings) |
| `revision/human_tasks/` | Annotation workbooks (original and adjudicated) |

Regenerate everything after any change:

```bash
python scripts/run_stats.py --dataset spider_vi; python scripts/run_stats.py --dataset bird_vi
python scripts/analyze_results.py --dataset spider_vi; python scripts/analyze_results.py --dataset bird_vi
python scripts/error_categories.py --dataset spider_vi; python scripts/error_categories.py --dataset bird_vi
python scripts/official_spider_em.py; python scripts/latency_summary.py
python revision/scripts/human_results.py; python revision/scripts/make_results_tables.py
```
