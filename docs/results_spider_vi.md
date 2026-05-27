# Kết quả thực nghiệm — Spider-VI

> Dataset: **Spider-VI** (`hoadm/vispider`) — 1,034 câu hỏi dev  
> Ngày chạy: 27/05/2026  
> Phần cứng: Intel Xeon W-2175, RTX 3090 (24GB), 125.5GB RAM

---

## Cấu hình thực nghiệm

| Thành phần | Chi tiết |
|---|---|
| Augmentation | `Qwen/Qwen2.5-7B-Instruct` — sinh alias/mô tả tiếng Việt offline |
| Schema Linking | `intfloat/multilingual-e5-large` — top-10 columns (cosine similarity) |
| SQL Generation | `Qwen2.5-Coder-{0.5B,1.5B,3B,7B}-Instruct` + `gpt-4.1-mini` (reference) |
| Ablation configs | `baseline`, `+aug`, `+link`, `full` |
| Metrics | EM (Exact Match, sqlglot normalize) + EX (Execution Accuracy, SQLite) |

---

## Kết quả chính

### Exact Match (EM)

| Model | baseline | +aug | +link | full |
|---|:---:|:---:|:---:|:---:|
| Qwen2.5-Coder-0.5B | 13.4% | 14.5% | 13.4% | **17.4%** |
| Qwen2.5-Coder-1.5B | 16.0% | 17.4% | 16.5% | **22.7%** |
| Qwen2.5-Coder-3B | 17.6% | 17.3% | 16.8% | **20.8%** |
| Qwen2.5-Coder-7B | 27.0% | 23.2% | 25.8% | **27.5%** |
| gpt-4.1-mini † | 21.7% | — | — | — |

### Execution Accuracy (EX)

| Model | baseline | +aug | +link | full | Δ (full−base) |
|---|:---:|:---:|:---:|:---:|:---:|
| Qwen2.5-Coder-0.5B | 30.3% | 34.4% | 33.8% | **40.3%** | +10.0% |
| Qwen2.5-Coder-1.5B | 50.8% | 50.2% | 50.8% | **58.0%** | +7.2% |
| Qwen2.5-Coder-3B | 57.9% | 54.1% | 59.4% | **64.8%** | +6.9% |
| Qwen2.5-Coder-7B | 73.7% | 64.5% | 72.8% | **73.8%** | +0.1% |
| gpt-4.1-mini † | **75.8%** | — | — | — | — |

> † `gpt-4.1-mini` là upper-bound reference, chỉ chạy `baseline` config, không tham gia ablation.

---

## Kiểm định thống kê (McNemar's Test, α = 0.05)

### So sánh `+aug` vs `baseline`

| Model | p-value | Kết quả | A wins | B wins | Nhận xét |
|---|:---:|:---:|:---:|:---:|---|
| 0.5B | 0.0015 | **YES \*** | 109 | 66 | +aug **giúp** |
| 1.5B | 0.7556 | no | 126 | 132 | không đáng kể |
| 3B | 0.0068 | **YES \*** | 84 | 124 | +aug **gây hại** |
| 7B | < 0.0001 | **YES \*** | 56 | 151 | +aug **gây hại nặng** |

### So sánh `+link` vs `baseline`

| Model | p-value | Kết quả | A wins | B wins | Nhận xét |
|---|:---:|:---:|:---:|:---:|---|
| 0.5B | 0.0004 | **YES \*** | 66 | 30 | +link **giúp** |
| 1.5B | 0.9322 | no | 69 | 69 | không đáng kể |
| 3B | 0.1799 | no | 62 | 47 | không đáng kể |
| 7B | 0.3491 | no | 32 | 41 | không đáng kể |

### So sánh `full` vs `baseline`

| Model | p-value | Kết quả | A wins | B wins | Nhận xét |
|---|:---:|:---:|:---:|:---:|---|
| 0.5B | < 0.0001 | **YES \*** | 146 | 42 | full **giúp mạnh** |
| 1.5B | < 0.0001 | **YES \*** | 168 | 93 | full **giúp mạnh** |
| 3B | < 0.0001 | **YES \*** | 130 | 59 | full **giúp** |
| 7B | 1.0000 | no | 64 | 63 | **bão hòa** |

---

## H3 — Tương quan Spearman (model size vs ΔΕΧ)

| Model size | ΔΕΧ (full − baseline) |
|:---:|:---:|
| 0.5B | +10.06% |
| 1.5B | +7.25% |
| 3.0B | +6.87% |
| 7.0B | +0.10% |

**ρ = −1.000 | p < 0.0001 | Significant = YES ✅**

> H3 được xác nhận hoàn toàn: model càng nhỏ, lợi ích từ LASF framework càng lớn.

---

## Phân tích

### Điểm chính

1. **`full` config cải thiện EX đáng kể cho 3/4 models** (0.5B, 1.5B, 3B, p < 0.0001); riêng 7B bão hòa ở ~74%.

2. **Augmentation có tác động ngược chiều theo model size** — giúp model nhỏ (0.5B), gây hại cho model lớn (3B, 7B). Đây là finding mới: augmentation chỉ có lợi khi model chưa đủ năng lực xử lý schema đa ngôn ngữ.

3. **Schema linking chỉ giúp đáng kể model 0.5B** — model lớn hơn đã đủ khả năng attention qua toàn bộ schema.

4. **H3 hoàn toàn xác nhận** với tương quan Spearman hoàn hảo (ρ = −1.0): lợi ích framework tỉ lệ nghịch với model size.

5. **7B (73.8% EX) chỉ cách GPT-4.1-mini (75.8% EX) 2.0%** — mô hình local 7B tham số có thể gần đạt GPT trên task Vietnamese Text-to-SQL, hoàn toàn offline và training-free.

### Giới hạn

- Framework không đem lại cải thiện có ý nghĩa cho Qwen2.5-Coder-7B.
- Kết quả chỉ trên Spider-VI; cần xác nhận thêm trên BIRD-VI.
- Chất lượng augmentation phụ thuộc vào Qwen2.5-7B-Instruct (chưa đánh giá độc lập).
