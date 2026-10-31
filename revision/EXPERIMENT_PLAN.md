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
| B1 | ~~Lấy lại `augmented_schemas` cũ~~ → **Đã quyết định sinh lại** (29/10): bản cũ không còn | — | Sinh lại với seed 2026, seed riêng cho từng bảng nên kết quả không phụ thuộc thứ tự chạy. Mọi config có aug đều chạy lại. Metadata trong bài (Table 1, các ví dụ) cần lấy từ bản mới. Bản mới **được commit vào repo** (`augmentation/augmented_schemas/`), kèm `_stats_{dataset}.jsonl` ghi thời gian, VRAM và số token của từng DB (dùng cho E8) |
| B2 | Môi trường, dữ liệu, DB, Spider eval | ✅ 29/10 | torch 2.6.0+cu124, transformers 5.20.2, RTX 4090. Cần ghi lại phiên bản thư viện, vì v1 chạy với bản khác |
| B3 | API cho GPT-4.1-mini | ✅ 29/10 | Gọi qua **OpenRouter** (`openai/gpt-4.1-mini`), cố định nhà cung cấp là OpenAI, không fallback. Bài cần ghi rõ cách gọi này |

### Phát hiện thêm khi dựng lại (29/10)

- `download_data.py` lưu DB BIRD với đuôi `.db` trong khi loader tìm `.sqlite`. Mà `sqlite3.connect` gặp đường dẫn không tồn tại thì tạo DB rỗng, không báo lỗi. Đã sửa: lưu `.sqlite`, loader mở DB ở chế độ read-only và báo lỗi nếu thiếu file.
- v1 đưa cả bảng nội bộ `sqlite_sequence` vào schema/prompt. v2 đã loại ra. Sau khi loại: ViSpider **80 bảng / 439 cột** (Table 2 của bài ghi 81/441, tức đã đếm cả bảng nội bộ); ViBIRD 75 / 798, DB lớn nhất 199 cột, khớp với bài.

### Quyết định khi chạy qua đêm 29–30/10 (cần tác giả xem lại)

- **Augmentation theo nhóm cột.** Model sinh trung bình khoảng 64 token mỗi cột, nên `max_new_tokens=1024` chỉ đủ cho khoảng 16 cột. Bảng rộng hơn (ViBIRD có 9 bảng, `Match` 115 cột; ViSpider có 2 bảng) trả về JSON bị cắt, sau 3 lần thử thì bảng bị bỏ qua mà không có metadata, và code không báo lỗi. v1 dùng cùng cấu hình nên nhiều khả năng mắc lỗi này. v2 chia bảng >12 cột thành từng nhóm 12 cột (`augmentation.max_columns_per_call`). Bảng ≤12 cột giữ nguyên prompt và seed. Độ phủ metadata ghi ở `augmentation/augmented_schemas/_coverage.csv`.
- **Bản tải model đầu tiên thiếu `generation_config.json`.** File này chứa token dừng và các tham số sampling mặc định. Metadata sinh trước khi phát hiện đã bị xóa, và toàn bộ augmentation được sinh lại sau khi tải đủ model.
- **Prompt dài:** đã thử model 7B với prompt 32k token trên RTX 4090: 6.5 giây, VRAM tối đa 21.8GB. Nếu một batch tràn bộ nhớ thì tự chia nhỏ. Câu nào vẫn không vừa thì được ghi `oom` (số câu `n_oom` có trong `.meta.json`).
- **E5 dùng k ∈ {20, 30, 50}** cho ViBIRD, chọn theo kết quả recall (với k=10 chỉ 66.8% câu giữ đủ bảng vàng). ViSpider dùng k ∈ {5, 20}.
- Thứ tự chạy: `revision/scripts/run_queue.sh`; tiến độ ghi ở `logs/queue.log`.

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

---

## 8. Tiến độ và kết quả (cập nhật 30/10)

Số liệu chi tiết nằm trong `evaluation/analysis_v2/`; các con số dưới đây chỉ để định hướng, **chưa chốt**.

### Trạng thái

| Mục | Trạng thái | Output |
|---|---|---|
| B1 (sinh lại augmented schema) | Xong. ViSpider 439/439 cột, ViBIRD 796/798 | `augmentation/augmented_schemas/`, `_stats_*.jsonl` |
| C1–C9 | Xong (C7: EM chính thức của Spider có thêm script riêng) | |
| E1, E2, E3, E6 | Xong (E6 chạy cùng E1/E2) | `evaluation/results_v2/` |
| E4 | Xong cho e5-plain/e5-aug; BM25 và LLM-select chạy trong E7 | `analysis_v2/recall/` |
| E5, E7, E8, E9 | Xong 30/10 | `results_v2/`, `analysis_v2/latency/`, `analysis_v2/recall_baselines/` |
| A1, A2, A5, A6 | Xong (chạy lại trên số liệu cuối 30/10) | `analysis_v2/breakdown/` |
| A4 (C9) | Xong (chạy lại trên số liệu cuối 30/10) | `analysis_v2/stats/{dataset}_pairs.csv` |
| C7 EM chính thức Spider | Xong | `analysis_v2/official_em/` |
| A3, T3 | Xong; phiếu T3 đã giao | `analysis_v2/errors/`, `revision/human_tasks/T3_error_analysis/` |

Lệnh chạy lại các phân tích: `scripts/run_stats.py`, `scripts/analyze_results.py`, `scripts/official_spider_em.py` (mỗi lệnh `--dataset spider_vi|bird_vi` nếu có).

### Lưới thực tế khác kế hoạch (cần tác giả xem lại)

- E5: chạy k ∈ {20, 30, 50} trên ViBIRD (`+link`, `full` × 1.5B, 7B) và k ∈ {5, 20} trên ViSpider (`full` × 1.5B, 7B). Chọn theo E4: ở k=10 ViBIRD chỉ giữ đủ bảng vàng cho 67% câu, k=30 là 87%, k=50 là 92%.
- E9: thay vì bỏ hẳn sample values, cắt mỗi giá trị còn tối đa 50 ký tự (`--max_value_chars 50`), chỉ trên ViBIRD. Lý do: 10 cột XML của `european_football_2` chiếm 97,8% số ký tự sample values; prompt `+aug` của DB này giảm từ 43.659 xuống 12.618 token.
- E3 chạy cả ViSpider và ViBIRD với `baseline` và `full`.

### Kết quả chính đến 30/10 (EX %, k=10)

| | ViSpider baseline → full | ViBIRD baseline → full |
|---|---|---|
| 0.5B | 18,5 → 29,8 | 6,3 → 7,1 |
| 1.5B | 40,2 → 49,9 | 18,6 → 16,2 |
| 3B | 52,4 → 62,4 | 31,4 → 23,8 |
| 7B | 67,1 → 70,0 | 44,5 → 33,7 |
| GPT-4.1-mini | 73,2 → 70,5 | 50,7 → 35,8 |

- ViSpider: `+aug` và `full` hơn baseline có ý nghĩa thống kê (Holm) cho 0.5B–3B; 7B `full` chưa có ý nghĩa sau Holm (Δ +2,9, p_holm 0,17). `+link` và `augret` gần như không khác baseline; `augret` ≈ `+link` ở mọi model.
- ViBIRD: ở k=10 mọi config có linking thấp hơn baseline (trừ 0.5B), kể cả GPT-4.1-mini (−14,9). `+aug` cũng không giúp (7B −5,1): 129 câu của `european_football_2` vẫn bị cắt schema dù context 32k.
- E5 sơ bộ (ViBIRD): tăng k làm EX tăng đều. 1.5B `full` k=30 đạt 20,5 (> baseline 18,6, chưa có ý nghĩa). 7B `+link` k=30 đạt 38,5, vẫn thấp hơn baseline 44,5.
- A5: khi đủ bảng vàng, ViBIRD 7B `full` đạt 40,6 (vẫn < baseline 44,5), nên ngoài việc mất bảng còn mất cột cần thiết (recall cột ở k=10 chỉ 34%).
- A1: phần lớn SQL lỗi là `no such column` (model bịa cột), không phải lỗi cú pháp.
- E3: câu hỏi tiếng Anh cao hơn tiếng Việt 5–12 điểm trên ViSpider; mức tăng của `full` gần như giống nhau ở hai ngôn ngữ.

### Lưu ý khi viết

- EM chính thức của Spider: parser của Spider không đọc được 40–70% câu SQL do model sinh (alias bảng không có `AS` như `FROM stadium s`, alias cột trong SELECT), nên EM chính thức thấp hơn nhiều so với EX. Nên dùng EX làm chỉ số chính và nêu rõ hạn chế này.
- A5 trên ViBIRD: một số câu vẫn đúng dù “thiếu” bảng vàng, vì tập bảng vàng lấy từ gold SQL bằng sqlglot có thể dư (cột không ghi tên bảng được gán cho mọi bảng có cột đó) hoặc vì có câu SQL khác cho cùng kết quả.
- Server khởi động lại hai lần sáng 30/10; các run bị ngắt đã được chạy lại từ đầu, không dùng kết quả dở.

### Kết quả cuối của các thí nghiệm GPU (30/10)

- E5 ViBIRD, 7B `full`: k=10 33,7 · k=20 37,5 · k=30 40,7 · k=50 42,6 (baseline 44,5). 1.5B `full` cao nhất ở k=30 (20,5 > baseline 18,6, chưa có ý nghĩa). ViSpider 7B `full` k=20 đạt 72,1 (k=10: 70,0; baseline 67,1); k=5 giảm còn 64,2.
- E7, LLM chọn bảng (Qwen2.5-7B-Instruct, giữ toàn bộ cột của bảng được chọn, prompt thường) là cách lọc mạnh nhất:
  - ViBIRD: 0.5B 13,4 · 1.5B 23,9 · 3B 34,5 · 7B 45,6, đều ≥ baseline (có ý nghĩa với 0.5B–3B) và hơn `full` k=10 6–12 điểm.
  - ViSpider: 0.5B 31,9 · 1.5B 51,4 · 3B 60,3 · 7B 67,3, ngang `full` (khác biệt không có ý nghĩa).
  - Recall ViBIRD: giữ đủ bảng vàng 87,7% (e5-plain k=10: 66,8%) với trung bình 34 cột.
- E7, BM25 trên cột có metadata (`augret` với BM25): EX ngang `augret` với e5. Đáng chú ý là recall của bm25-aug cao hơn e5 (ViBIRD k=10: đủ bảng vàng 77,8% so với 65,5%).
- E9 (sample values ≤ 50 ký tự, ViBIRD): `+aug` tăng có ý nghĩa (7B 39,4 → 42,8; 3B 28,2 → 30,7), không còn câu nào bị cắt schema, nhưng vẫn chưa vượt baseline. `full` không đổi vì schema đã lọc vốn ngắn.
- E8 (batch 1, 200 câu): linking e5 khoảng 21 ms/câu; sinh SQL 1–2,6 s/câu với HF transformers (bị chi phối bởi overhead mỗi token, nên 7B không chậm hơn 3B). Peak VRAM `full` 7B 19,8 GB (ViBIRD). Augmentation offline: ViSpider 17,6 phút, ViBIRD 33,4 phút, peak 21,4 GB. LLM chọn bảng: 160–190 ms/câu khi chạy batch 8, peak 18,6 GB (không so trực tiếp với số batch 1). Bảng: `analysis_v2/latency/summary.csv`, `offline.csv`.

### E10 (thêm 30/10, tác giả đồng ý): `full` với LLM chọn bảng

Prompt có metadata tiếng Việt như `full`, nhưng lọc schema bằng LLM chọn bảng (cache của E7) thay cho e5 top-k cột; bảng được chọn giữ toàn bộ cột. Lưới: 4 model × 2 dataset (`full_llm_*`), cộng ViBIRD với sample values ≤ 50 ký tự (`full_llm_*_v50`). Chạy bằng `revision/scripts/run_queue4.sh`.

Gợi ý còn lại (chưa chạy): `full` với k theo tỉ lệ số cột (`--top_k_ratio`).

**Kết quả E10 (31/10), EX %** (baseline / `full` e5 k=10 / LLM chọn bảng không metadata / `full_llm`):

| | ViSpider | ViBIRD |
|---|---|---|
| 0.5B | 18,5 / 29,8 / 31,9 / **39,2** | 6,3 / 7,1 / 13,4 / 13,2 |
| 1.5B | 40,2 / 49,9 / 51,4 / **56,7** | 18,6 / 16,2 / 23,9 / **26,2** |
| 3B | 52,4 / 62,4 / 60,3 / **64,6** | 31,4 / 23,8 / 34,5 / **35,6** |
| 7B | 67,1 / 70,0 / 67,3 / **70,8** | 44,5 / 33,7 / 45,6 / **47,2** |

- `full_llm` hơn baseline có ý nghĩa (Holm) ở mọi model trên ViSpider và ở 0.5B–3B trên ViBIRD (7B: +2,7, p_holm 0,068).
- Thêm metadata vào prompt khi đã lọc bằng LLM (`full_llm` so với `pluslink_llm`): có ý nghĩa ở cả 4 model trên ViSpider (+3,5 đến +7,2); trên ViBIRD tăng +1,1 đến +2,3 nhưng chưa có ý nghĩa sau Holm.
- ViBIRD: 34 câu bị cắt schema (bảng chọn giữ đủ cột kèm metadata); bản `_v50` hết cắt nhưng EX không đổi.

### Kết quả người chấm T1–T3 (nhận 31/10)

File đã phân xử: `revision/human_tasks/final/*_best.xlsx` (2 người chấm độc lập, người thứ 3 phân xử khi bất đồng). Tổng hợp bằng `revision/scripts/human_results.py` → `evaluation/analysis_v2/human/`. κ tính lại khớp bảng tác giả gửi (κ không trọng số); có thêm κ trọng số tuyến tính và Gwet's AC1.

- T1 (bản dịch, 100 + 100 câu): độ chính xác nghĩa trung bình 2,84 (ViSpider) và 2,87 (ViBIRD); 85% và 89% đạt điểm 3. Lỗi làm SQL phải khác: 1% và 2%. Độ tự nhiên 2,48 và 2,57. Evidence ViBIRD: 2,94 (95,5% đạt 3, n = 89 câu có evidence).
- T2 (metadata, 200 cột + 155 bảng): tên tiếng Việt 2,25; từ đồng nghĩa 2,02; mô tả 2,35; tên bảng 2,21. 41,5% cột bị đánh giá "có thể gây nhầm cột" (ViBIRD 46,7%, ViSpider 33,8%). ViBIRD thấp hơn ViSpider ở mọi tiêu chí.
- T3 (120 lỗi): nhãn tự động khớp nhãn người 73,1% (nhóm A 76,9%, B 85,0%, C 57,5%). 19/120 câu (15,8%) có câu hỏi hoặc SQL tham chiếu có vấn đề.
- κ thấp ở "Lỗi ảnh hưởng SQL?" (0,49) và "evidence" (0,27) do một giá trị chiếm 95–99% (nghịch lý κ); đồng thuận thô 86–99%, AC1 0,85–0,99. Nên báo cáo cả đồng thuận thô và AC1. "Dùng làm ví dụ" (κ 0,17) không đưa vào bài.
- Còn 7 ô chưa thống nhất (T1 loại lỗi: 6; T3 nhãn lỗi: 1), không ảnh hưởng các con số chính.
