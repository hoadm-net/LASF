# Kế hoạch thực nghiệm — bản sửa JICT

> Hạn nộp bản sửa: **15/11/2026**. Mốc chốt số liệu cho phần viết: **08/11/2026**.
> Phạm vi file này: chỉ thực nghiệm và phân tích. Phần viết lại bài và rebuttal làm riêng.

---

## 0. Nguyên tắc

1. **Giữ nguyên phương pháp**: prompt template, cách dựng column document, cách giữ PK/FK và prompt augmentation không đổi. Chỉ sửa lỗi pipeline (mục 2). Chỗ nào bài báo mô tả khác code thì sửa bài cho khớp code.
2. **Một phiên bản code cho mọi con số trong bài.** Toàn bộ lưới chính được chạy lại bằng code v2 và lưu vào `evaluation/results_v2/`. Kết quả v1 (`evaluation/results/`) giữ nguyên để đối chiếu.
3. **Kết quả v1 của `spider_vi` thực chất dùng câu hỏi tiếng Anh**: `download_data.py` lấy `dev.json` (Spider gốc), còn `load_spider_vi` đọc trường `question`. Trong v2, bộ này được gắn nhãn lại là `spider_en` và dùng làm dự phòng cho E3.
4. Mọi run đều ghi kèm file `.meta.json` gồm commit hash, GPU, phiên bản thư viện, tham số và thời gian chạy.

---

## 1. Việc chặn (cần xử lý trước)

| ID | Việc | Ai | Ghi chú |
|---|---|---|---|
| B1 | **Lấy lại `augmentation/augmented_schemas/`** (20 DB ViSpider + 11 DB ViBIRD) từ máy chạy v1 (RTX 3090) | Tác giả | Thư mục này bị `.gitignore` nên máy hiện tại không có. Dùng lại đúng file cũ thì metadata trong bài, trong T2 và trong mọi run sẽ thống nhất. Nếu buộc phải sinh lại thì kết quả sẽ khác bản cũ, vì augmentation dùng `do_sample=True, temperature=0.1`. Khi đó cần ghi seed và chạy lại mọi config có aug |
| B2 | Dựng môi trường, tải DB Spider và BIRD, tải `vispider_dev.json` / `vibird_dev.json`, cài `third_party/spider` | Máy | |
| B3 | `OPENAI_API_KEY` trong `.env` | Tác giả | Cho E1 (GPT baseline) và E6 |

---

## 2. Sửa code (trước khi chạy)

| ID | Thay đổi | File | Phục vụ |
|---|---|---|---|
| C1 | Tải trực tiếp `vispider_dev.json` và `vibird_dev.json`. Loader thêm tham số `--question_lang {vi,en}`: Spider đọc `question_vi`/`question`, BIRD đọc `question_vi`+`evidence_vi` hoặc `question`+`evidence`. Lưu thêm `sql_class` và `difficulty` vào output | `scripts/download_data.py`, `utils/data_loader.py`, `run_experiment.py` | Sửa lỗi; E3; phân tích theo độ khó |
| C2 | Thay truncation: đặt `--max_input_tokens` (mặc định 32768, đúng context của Qwen2.5-Coder). Khi prompt vượt giới hạn, **cắt phần schema** (bỏ dần cột/bảng ở cuối) và giữ nguyên instruction, evidence, question. Mỗi ví dụ ghi `prompt_tokens` và `truncated` | `generation/sql_generator.py`, `prompts/templates.py` | R2 major 1 |
| C3 | Ghi đo đạc: `prompt_tokens`, `output_tokens`, thời gian mỗi batch, peak GPU memory (`torch.cuda.max_memory_allocated`). Sắp ví dụ theo độ dài prompt và chia batch theo ngân sách token để prompt dài 32k không bị OOM | `run_experiment.py`, `generation/sql_generator.py` | E8; tốc độ chạy |
| C4 | Tách augmentation thành hai cờ: `aug_retrieval` (dùng metadata khi linking) và `aug_prompt` (đưa metadata vào prompt). Thêm config **`augret`** = linking có aug + prompt thường đã lọc | `run_experiment.py` | R2 major 3 |
| C5 | Tham số `--top_k` và `--top_k_ratio` (k tính theo tỉ lệ số cột của DB) | `linking/schema_linker.py`, `run_experiment.py` | E4, E5 |
| C6 | Hai linker baseline, đều training-free: **BM25** trên column document, và **chọn bảng bằng LLM** (Qwen2.5-7B-Instruct, zero-shot, kiểu C3/CHESS: model chọn bảng, giữ toàn bộ cột của bảng được chọn) | `linking/bm25_linker.py`, `linking/llm_table_selector.py` | R2 major 6 |
| C7 | Đánh giá: ghi trạng thái thực thi của pred (`ok` / `error` / `timeout`) để tính tỉ lệ invalid SQL. Thêm EM chính thức của Spider và hardness qua `third_party/spider/evaluation.py`, bên cạnh EM bằng sqlglot | `evaluation/metrics.py`, `scripts/run_eval.py` | R2 major 8a, 8b, 9 |
| C8 | Script recall: phân tích gold SQL bằng sqlglot (giải alias) ra tập bảng/cột vàng, rồi đo recall sau filtering | `scripts/retrieval_recall.py` | E4 |
| C9 | Thống kê: McNemar cho **mọi cặp config** theo từng model và dataset, hiệu chỉnh Holm trong mỗi họ kiểm định; paired bootstrap 95% CI cho ΔEX (10.000 lần lấy mẫu). Bỏ Spearman | `evaluation/stats.py`, `scripts/run_stats.py` | R2 major 8c, 8d |

Kiểm tra sau khi sửa: chạy 20 câu mỗi dataset, xác nhận câu hỏi là tiếng Việt, `truncated` hợp lý, và kết quả config `baseline` của v1 và v2 trên ViBIRD gần nhau.

---

## 3. Danh sách thực nghiệm

Ký hiệu: **P0** bắt buộc, **P1** reviewer yêu cầu trực tiếp, **P2** làm nếu còn thời gian.
Model: 0.5B / 1.5B / 3B / 7B = Qwen2.5-Coder-*-Instruct.
Config chính (5): `baseline`, `+aug`, `+link`, `augret`, `full`.

| ID | Thực nghiệm | Lưới chạy | Số run | Ưu tiên | Trả lời |
|---|---|---|---|---|---|
| **E1** | ViSpider câu hỏi **tiếng Việt** | 4 model × 5 config + GPT-4.1-mini `baseline` | 21 | P0 | Lỗi v1 |
| **E2** | ViBIRD, code v2 (context 32k, cắt phía schema) | 4 model × 5 config + GPT-4.1-mini `baseline` | 21 | P0 | R2 major 1 |
| **E3** | Câu hỏi **tiếng Anh** (đo khoảng cách cross-lingual) | Spider-EN và BIRD-EN × 4 model × {`baseline`, `full`} | 16 | P1 | R2 major 6 |
| **E4** | **Recall** của schema filtering (không sinh SQL) | linker {e5-plain, e5-aug, bm25-plain, bm25-aug, llm-select} × k {5, 10, 15, 20, 30, 50} và ratio {0.15, 0.25, 0.45} × 2 dataset | 0 GPU-gen | P0 | R2 major 2; chọn k cho E5 |
| **E5** | Độ nhạy theo **k** khi sinh SQL | ViBIRD: {`+link`, `full`} × k {5, 20, 30, ratio 0.45} × {1.5B, 7B} = 16; ViSpider: `full` × k {5, 20, ratio 0.45} × {1.5B, 7B} = 6 | 22 | P1 | R2 major 1 |
| **E6** | GPT-4.1-mini ở config **`full`** | 2 dataset | 2 | P1 | R2 major 6 |
| **E7** | Baseline schema filtering có sẵn (prompt thường) | {BM25, LLM-select} × 4 model × 2 dataset (nếu thiếu thời gian: chỉ 1.5B và 7B) | 16 (8) | P1 | R2 major 6 |
| **E8** | **Hiệu năng** ("lightweight") | 200 câu/dataset, batch=1, 4 model × {`baseline`, `full`}: latency p50/p95, peak VRAM, số token prompt. Linker: thời gian encode. Augmentation: thời gian và VRAM mỗi DB (chạy lại trên 3 DB nhỏ/vừa/lớn) | 16 nhỏ | P1 | R2 major 7 |
| E9 | Tách sample values khỏi metadata tiếng Việt | `+aug` và `full` không có sample values, × 4 model × 2 dataset | 16 | P2 | Làm rõ ablation |

Tổng P0+P1: khoảng 98 run sinh SQL. Run ViSpider ngắn. Phần tốn thời gian nhất là các run ViBIRD có aug ở context dài, đặc biệt 7B.

### Phân tích không cần GPU (sau E1, E2)

| ID | Phân tích | Trả lời |
|---|---|---|
| A1 | Tỉ lệ invalid SQL (lỗi cú pháp, lỗi thực thi, timeout) theo model, config, dataset | R2 major 8b |
| A2 | EX theo độ khó: Spider hardness (easy/medium/hard/extra) và BIRD `difficulty` (simple/moderate/challenging); thêm theo `sql_class` | R2 major 9 |
| A3 | Phân loại lỗi tự động: invalid SQL / thiếu bảng vàng trong prompt / chọn sai bảng / sai cột / sai điều kiện hoặc giá trị / sai aggregation hoặc GROUP BY / sai ORDER/LIMIT / lỗi khác. Sau đó lấy mẫu cho người xem (T3) | R2 major 9 |
| A4 | Thống kê C9 cho toàn bộ kết quả: bảng McNemar và Holm đầy đủ, CI cho Δ | R2 major 8c, 8d |
| A5 | Liên hệ recall (E4) với EX: EX khi đủ hoặc thiếu bảng vàng; tỉ lệ cột được giữ (ViSpider khoảng 45% so với ViBIRD khoảng 14% ở k=10) | R2 major 1, 2 |
| A6 | Thống kê độ dài prompt và tỉ lệ prompt bị cắt theo config/dataset (v2 so với v1 ở 4096) | R2 major 1 |

---

## 4. Việc cần người làm (thư mục `revision/human_tasks/`)

| ID | Việc | Phụ thuộc | Giao | Nhận lại |
|---|---|---|---|---|
| T1 | Kiểm tra chất lượng bản dịch ViSpider/ViBIRD (200 câu, 2 người chấm) | Không | 30/10 | 05/11 |
| T2 | Kiểm tra metadata tiếng Việt do LLM sinh (2 người chấm) | B1 | Ngay sau B1 | 07/11 |
| T3 | Xem tay mẫu lỗi để kiểm chứng phân loại tự động và chọn ví dụ | E1, E2, A3 | khoảng 07/11 | 10/11 |

Độ đồng thuận giữa hai người chấm (Cohen's κ, có trọng số cho thang thứ bậc) tính bằng `revision/scripts/agreement.py` sau khi nhận file.

---

## 5. Thứ tự và lịch

| Ngày | Việc |
|---|---|
| 29–30/10 | B1–B3; C1, C2, C3, C8; giao T1 |
| 30–31/10 | E4 (recall, chọn k); C4–C7, C9; kiểm tra nhanh |
| 31/10–03/11 | E1 (nhanh) → E2 → E3 |
| 03–06/11 | E7, E5, E6, E8; giao T2 khi có B1 |
| 06–08/11 | A1–A6; giao T3; **chốt số liệu 08/11** |
| 08–10/11 | Nhận T1–T3, tính κ, bổ sung số vào bảng; E9 nếu còn thời gian |

Sau run đầu tiên của mỗi dataset sẽ đo thời gian thực tế. Nếu không kịp, cắt theo thứ tự: E9 → E7 chỉ giữ 1.5B và 7B → E5 bỏ ViSpider → E3 chỉ giữ `baseline`.

---

## 6. Quy ước output

```
evaluation/results_v2/{dataset}/{config}[_k{k}|_r{ratio}][_{linker}][_en]_{model}.jsonl
evaluation/results_v2/{dataset}/{...}.meta.json
evaluation/analysis_v2/            # bảng, hình, số liệu thống kê
```

Mỗi dòng JSONL thêm các trường: `question_lang`, `difficulty`/`sql_class`, `prompt_tokens`, `truncated`, `n_cols_kept`, `n_cols_total`, `exec_status`, `latency_ms`.

---

## 7. Đối chiếu với comment

| Comment | Thực nghiệm / phân tích |
|---|---|
| R2 major 1 (truncation, k cố định) | C2, E2, E4, E5, A5, A6 |
| R2 major 2 (recall) | C8, E4, A5 |
| R2 major 3 (tách tác động của aug) | C4, `augret` trong E1/E2; E9 |
| R2 major 4 (claim về 7B) | Số liệu từ E1 (phần viết) |
| R2 major 5 (nguồn dữ liệu, chất lượng dịch) | T1 |
| R2 major 6 (baseline) | E3, E6, E7 |
| R2 major 7 (lightweight) | E8 |
| R2 major 8 (EM, invalid SQL, McNemar, Spearman) | C7, C9, A1, A4 |
| R2 major 9 (phân tích lỗi) | A2, A3, T3 |
| R2 3.5 (metadata chưa được người kiểm) | T2 |
| R2 minor 4 / R1 4.5 (Figure 2) | Vẽ lại từ `analysis_v2` |
