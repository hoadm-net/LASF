# Kết quả thực nghiệm — BIRD-VI

> Dataset: **BIRD-VI** (`hoadm/vibird`) — 1,534 câu hỏi dev, 11 cơ sở dữ liệu SQLite  
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
| Qwen2.5-Coder-0.5B | 0.9% | 0.6% | **1.2%** | **1.2%** |
| Qwen2.5-Coder-1.5B | **3.6%** | 2.0% | 2.2% | 2.7% |
| Qwen2.5-Coder-3B | **6.8%** | 2.7% | 3.7% | 4.4% |
| Qwen2.5-Coder-7B | **4.9%** | 1.6% | 3.4% | 3.2% |
| gpt-4.1-mini † | **4.3%** | — | — | — |

### Execution Accuracy (EX)

| Model | baseline | +aug | +link | full | Δ (full−base) |
|---|:---:|:---:|:---:|:---:|:---:|
| Qwen2.5-Coder-0.5B | 5.7% | 2.7% | 6.4% | **7.0%** | +1.4% |
| Qwen2.5-Coder-1.5B | **18.6%** | 10.0% | 14.7% | 16.2% | -2.5% |
| Qwen2.5-Coder-3B | **31.5%** | 16.4% | 20.1% | 22.8% | -8.7% |
| Qwen2.5-Coder-7B | **44.1%** | 24.1% | 31.0% | 33.9% | -10.2% |
| gpt-4.1-mini † | **50.1%** | — | — | — | — |

> † `gpt-4.1-mini` là upper-bound reference, chỉ chạy `baseline` config, không tham gia ablation.

---

## Kiểm định thống kê (McNemar's Test, α = 0.05)

### So sánh `+aug` vs `baseline`

| Model | p-value | Kết quả | A wins | B wins | Nhận xét |
|---|:---:|:---:|:---:|:---:|---|
| 0.5B | < 0.0001 | **YES \*** | 26 | 72 | +aug **gây hại** |
| 1.5B | < 0.0001 | **YES \*** | 65 | 197 | +aug **gây hại mạnh** |
| 3B | < 0.0001 | **YES \*** | 69 | 300 | +aug **gây hại rất mạnh** |
| 7B | < 0.0001 | **YES \*** | 77 | 385 | +aug **gây hại rất mạnh** |

### So sánh `+link` vs `baseline`

| Model | p-value | Kết quả | A wins | B wins | Nhận xét |
|---|:---:|:---:|:---:|:---:|---|
| 0.5B | 0.3149 | no | 55 | 44 | tăng nhẹ nhưng **không đáng kể** |
| 1.5B | 0.0001 | **YES \*** | 87 | 147 | +link **gây hại** |
| 3B | < 0.0001 | **YES \*** | 68 | 242 | +link **gây hại mạnh** |
| 7B | < 0.0001 | **YES \*** | 64 | 266 | +link **gây hại mạnh** |

### So sánh `full` vs `baseline`

| Model | p-value | Kết quả | A wins | B wins | Nhận xét |
|---|:---:|:---:|:---:|:---:|---|
| 0.5B | 0.0690 | no | 71 | 50 | full **giúp nhẹ**, chưa đủ ý nghĩa thống kê |
| 1.5B | 0.0238 | **YES \*** | 115 | 153 | full **gây hại** |
| 3B | < 0.0001 | **YES \*** | 92 | 226 | full **gây hại mạnh** |
| 7B | < 0.0001 | **YES \*** | 106 | 263 | full **gây hại mạnh** |

---

## H3 — Tương quan Spearman (model size vs ΔEX)

| Model size | ΔEX (full − baseline) |
|:---:|:---:|
| 0.5B | +1.37% |
| 1.5B | -2.48% |
| 3.0B | -8.74% |
| 7.0B | -10.23% |

**ρ = −1.000 | p < 0.0001 | Significant = YES ✅**

> H3 vẫn được xác nhận về mặt xu hướng tương đối: model càng nhỏ càng có nhiều khả năng hưởng lợi từ LASF. Tuy nhiên, trên BIRD-VI điều này **không** có nghĩa là mọi model đều được cải thiện; thực tế chỉ 0.5B được lợi nhẹ, còn các model lớn hơn bị giảm hiệu năng.

---

## Error Analysis on Compact vs Large Schemas

Để kiểm tra giả thuyết rằng LASF vẫn hữu ích trên các schema nhỏ nhưng suy giảm khi gặp schema lớn/phức tạp, chúng tôi chia 11 database của BIRD-VI theo **độ dài prompt augmented** (số token của prompt `+aug`/`full`, đo bằng tokenizer của Qwen2.5-Coder-7B).

- **Small**: `< 2000` tokens
- **Medium**: `2000-4999` tokens
- **Large**: `>= 5000` tokens

### Phân nhóm schema

| Bucket | Databases |
|---|---|
| Small | `toxicology`, `debit_card_specializing`, `superhero` |
| Medium | `thrombosis_prediction`, `financial`, `california_schools`, `student_club`, `codebase_community` |
| Large | `formula_1`, `card_games`, `european_football_2` |

### Delta EX trung bình theo bucket

| Bucket | mean(`full`−`baseline`) | mean(`+link`−`baseline`) | mean(`+aug`−`baseline`) |
|---|:---:|:---:|:---:|
| Small | **+0.003** | -0.054 | **+0.050** |
| Medium | -0.062 | -0.057 | -0.066 |
| Large | -0.052 | -0.092 | **-0.271** |

### Delta EX theo model và bucket

| Model | Small `full−base` | Medium `full−base` | Large `full−base` |
|---|:---:|:---:|:---:|
| 0.5B | **+0.041** | -0.001 | **+0.013** |
| 1.5B | **+0.018** | -0.028 | -0.028 |
| 3B | -0.041 | -0.095 | -0.095 |
| 7B | -0.007 | -0.126 | -0.097 |

| Model | Small `+aug−base` | Medium `+aug−base` | Large `+aug−base` |
|---|:---:|:---:|:---:|
| 0.5B | **+0.025** | -0.016 | -0.088 |
| 1.5B | **+0.077** | -0.060 | -0.203 |
| 3B | **+0.036** | -0.088 | -0.335 |
| 7B | **+0.061** | -0.099 | -0.459 |

### Nhận xét

1. **Thành phần augmentation vẫn có tín hiệu dương trên compact schemas.** Ở bucket small, `+aug` cải thiện EX trung bình cho cả bốn model; hiệu ứng này biến mất ở bucket medium và đảo chiều rất mạnh ở bucket large.

2. **`full` chỉ giữ được lợi ích ở model nhỏ hơn.** Với 0.5B và 1.5B, `full` còn dương trong bucket small; từ 3B trở lên, `full` không còn lợi ngay cả trên compact schemas.

3. **`+link` không cho thấy lợi ích ổn định ngay cả trên schema nhỏ.** Điều này cho thấy bottleneck chính của LASF trên BIRD-VI không chỉ nằm ở schema size, mà còn ở chiến lược cắt schema theo `top_k=10` columns.

4. **Schema size/prompt size là một phần câu chuyện, nhưng không phải toàn bộ.** Tương quan Spearman giữa `full−baseline` và các chỉ số kích thước schema (`#columns`, raw prompt tokens, augmented prompt tokens) đều âm nhưng chưa mạnh trên chỉ 11 database. Vì vậy, kết luận an toàn hơn là: *LASF suy giảm rõ rệt khi schema và prompt augmentation trở nên lớn hơn, nhưng hiệu năng còn phụ thuộc thêm vào chất lượng metadata augmentation và độ chính xác của schema linking.*

### Diễn giải lỗi

- Ở bucket large, augmentation làm prompt phình rất mạnh. Ví dụ, `european_football_2` đạt khoảng **37k tokens** ở prompt augmented, vượt cả context window 32k của Qwen2.5-Coder, trong khi pipeline hiện tại còn cắt ở **4096 tokens**. Điều này khiến `+aug` và `full` dễ mất thông tin quan trọng.
- Với `+link` và `full`, bộ truy hồi theo cột có thể loại luôn bảng cần thiết cho gold SQL. Trong các ca `baseline đúng / +link sai` của model 7B, gần **49.2%** câu hỏi bị thiếu ít nhất một gold table sau bước linking.
- Trên các schema nhỏ hơn, augmentation có thể vẫn giúp bằng cách cung cấp thêm tín hiệu song ngữ. Tuy nhiên, khi schema lớn lên, lượng alias, sample values, và description bổ sung dường như tạo nhiễu nhanh hơn lợi ích mà chúng mang lại.

### Kết luận của subgroup analysis

Phân tích này **không đủ** để khẳng định LASF luôn đúng trên schema nhỏ và chỉ thất bại trên schema lớn. Tuy nhiên, nó ủng hộ một phiên bản yếu hơn nhưng hợp lý hơn của giả thuyết ban đầu:

> **LASF, đặc biệt là augmentation, vẫn có ích trong regime schema gọn và model nhỏ; nhưng khi schema lớn hơn, prompt inflation và schema pruning làm lợi ích này biến mất hoặc đảo chiều.**

Điều này giúp bảo toàn luận điểm cốt lõi của framework ở setting phù hợp, đồng thời bổ sung một phát hiện mới quan trọng về **boundary conditions** của LASF trên benchmark khó hơn như BIRD-VI.

---

## Phân tích

### Điểm chính

1. **`baseline` là cấu hình mạnh nhất trên BIRD-VI cho 3/4 local models** (1.5B, 3B, 7B). Đây là kết quả ngược với Spider-VI, nơi `full` thường thắng.

2. **`full` chỉ giúp nhẹ cho model 0.5B** (+1.37 điểm EX), nhưng cải thiện này chưa đạt ý nghĩa thống kê (p = 0.0690). Từ 1.5B trở lên, `full` làm giảm EX có ý nghĩa thống kê.

3. **Augmentation là thành phần bất ổn nhất trên BIRD-VI**. Ở phân tích toàn bộ benchmark, `+aug` giảm EX trên cả 4 model; tuy nhiên subgroup analysis cho thấy nó vẫn còn tín hiệu dương trên compact schemas. Điều này gợi ý rằng augmentation không thất bại hoàn toàn, mà thất bại khi bước sang regime schema lớn hoặc prompt quá dài.

4. **Schema linking hiện là bottleneck kỹ thuật rõ nhất của LASF trên BIRD-VI**. `+link` chỉ có ích rất hạn chế cho 0.5B, còn từ 1.5B trở lên đều giảm EX đáng kể. Kết quả này phù hợp với error analysis ở trên: bộ truy hồi theo cột đang cắt schema quá mạnh trong nhiều truy vấn nhiều bảng.

5. **Khoảng cách giữa local best và GPT reference vẫn tương đối nhỏ ở đầu trên**: `Qwen2.5-Coder-7B baseline` đạt 44.1% EX, thấp hơn `gpt-4.1-mini baseline` 6.0 điểm. Trong bối cảnh BIRD-VI khó hơn Spider-VI, đây vẫn là mức cạnh tranh tốt cho một hệ local, offline, training-free.

6. **BIRD-VI cho thấy LASF không phải là cải thiện phổ quát, mà là một framework có boundary conditions rõ ràng**. Trên benchmark khó, schema-aware enhancement cần được điều tiết theo độ lớn schema, độ dài prompt, và năng lực model; nếu không, lượng context bổ sung có thể làm mô hình lệch khỏi tín hiệu thật trong câu hỏi.

### Diễn giải khả dĩ

- BIRD-VI có schema lớn hơn và nhiều cột nhiễu hơn Spider-VI, nên LASF dễ đi từ “bổ sung ngữ nghĩa” sang “bổ sung nhiễu”.
- Model nhỏ nhất (0.5B) vẫn hưởng lợi phần nào từ tín hiệu bổ sung vì bản thân nó thiếu năng lực suy diễn schema thuần túy.
- Model lớn hơn có thể đã đủ khả năng xử lý raw schema; khi thêm alias, mô tả, sample values, hoặc top-k linked columns, prompt dài hơn nhưng không nhất thiết giàu thông tin hơn.
- Vì vậy, kết quả trên BIRD-VI không phủ định LASF, mà cho thấy framework này cần cơ chế **adaptive control** theo schema regime thay vì áp dụng cùng một mức augmentation/linking cho mọi database.

### Giới hạn

- Kết quả BIRD-VI chỉ mới kiểm tra một cách cài đặt LASF hiện tại; chưa thử các biến thể như giới hạn augmentation, rút gọn evidence, hay schema linking chọn lọc hơn.
- McNemar cho thấy nhiều khác biệt có ý nghĩa thống kê, nhưng chưa chỉ ra trực tiếp nguyên nhân lỗi nằm ở augmentation, linking, hay interaction giữa hai thành phần.
- Cần phân tích lỗi định tính thêm trên một mẫu truy vấn thất bại để xác nhận vì sao `full` kém hơn `baseline` ở các model lớn.