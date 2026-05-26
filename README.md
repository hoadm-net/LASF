# LSAF: A Lightweight Schema-Aware Framework for Vietnamese Text-to-SQL

## Tổng quan

Framework nhằm cải thiện hiệu quả bài toán Vietnamese Text-to-SQL trong bối cảnh:

- Câu hỏi bằng tiếng Việt
- Schema và SQL bằng tiếng Anh
- Thiết lập **zero-shot** trên các schema chưa từng xuất hiện
- Hoàn toàn **training-free**, không phụ thuộc API ngoài

---

## Giả thuyết nghiên cứu

| ID | Nội dung |
|----|----------|
| H1 | Schema augmentation (alias tiếng Việt, synonym, sample values) giúp mô hình lựa chọn đúng bảng và cột liên quan |
| H2 | Schema linking giúp giảm nhiễu ngữ cảnh và cải thiện chất lượng sinh SQL |
| H3 | Các kỹ thuật schema-aware mang lại hiệu quả lớn hơn (delta tuyệt đối) đối với các mô hình nhỏ |

---

## Câu hỏi nghiên cứu

| ID | Nội dung |
|----|----------|
| RQ1 | Schema augmentation có cải thiện hiệu quả Vietnamese Text-to-SQL hay không? |
| RQ2 | Schema linking có giúp giảm lỗi schema grounding và tăng execution accuracy hay không? |
| RQ3 | Hiệu quả của schema-aware enhancement thay đổi như thế nào theo kích thước mô hình? |

---

## Kiến trúc Framework

```text
Vietnamese Question
        │
        ▼
┌─────────────────────────────────────────┐
│  OFFLINE — Qwen2.5-7B-Instruct          │
│  Schema Augmentation                    │
│  (alias VI, synonym, sample values,     │
│   column description)                   │
│  → Chạy 1 lần / schema, không tốn       │
│    chi phí per-query                    │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│  ONLINE — multilingual-e5               │
│  Schema Linking                         │
│  (embed question + augmented schema     │
│   → cosine similarity → top-k           │
│   tables/columns)                       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│  ONLINE — Qwen2.5-Coder-xB             │
│  SQL Generation                         │
│  (prompt = question + retrieved schema) │
└─────────────────────────────────────────┘
        │
        ▼
   Generated SQL
```

---

## Chi tiết các thành phần

### 1. Schema Augmentation (Offline)

**Model:** `Qwen2.5-7B-Instruct` — chạy local, một lần duy nhất cho mỗi schema.

Mỗi table/column được mở rộng với các trường:

| Trường | Mô tả | Ví dụ |
|--------|-------|-------|
| `alias_vi` | Tên tiếng Việt | `students` → `"sinh viên"` |
| `synonym` | Từ đồng nghĩa tiếng Việt | `gpa` → `["điểm trung bình", "học lực"]` |
| `sample_values` | Lấy trực tiếp từ database | `["Hanoi", "HCM", "Danang"]` |
| `description` | Mô tả ngắn 1 câu | `"Cột lưu điểm trung bình tích lũy của sinh viên"` |

Output là JSON có cấu trúc, dễ validate và tái sử dụng.

### 2. Schema Linking (Online)

**Model:** `intfloat/multilingual-e5-large` (hoặc `multilingual-e5-base` nếu cần nhẹ hơn)

- Đơn vị retrieval: **column-level** (mỗi column là một document, kèm table context)
- Embed câu hỏi tiếng Việt và các augmented schema elements (VI aliases + EN names)
- Tính cosine similarity → chọn top-k columns/tables liên quan nhất

> **Lý do chọn hướng này:** Augmentation sinh alias tiếng Việt giúp retrieval match VI↔VI thay vì VI↔EN, cải thiện trực tiếp chất lượng schema linking.

### 3. SQL Generation (Online)

**Models được đánh giá:**

| Model | Tham số |
|-------|---------|
| `Qwen2.5-Coder-0.5B-Instruct` | 0.5B |
| `Qwen2.5-Coder-1.5B-Instruct` | 1.5B |
| `Qwen2.5-Coder-3B-Instruct` | 3B |
| `Qwen2.5-Coder-7B-Instruct` | 7B |

Input prompt: câu hỏi tiếng Việt + schema đã được augment và filter (top-k retrieved).

---

## Dataset

Cả hai dataset được dịch sang tiếng Việt bằng pipeline đặc biệt, đã công bố trong công trình riêng.

| Dataset | Gốc | Phiên bản dùng |
|---------|-----|----------------|
| Spider | Yu et al., 2018 | Vietnamese-translated Spider |
| BIRD | Li et al., 2023 | Vietnamese-translated BIRD |

**Tập đánh giá:** Dev set (training-free → không có nguy cơ data leakage, không cần test split).

> *"We evaluate on the dev set as our approach is training-free and involves no parameter optimization on any split."*

---

## Metrics

| Metric | Mô tả |
|--------|-------|
| **EM** | Exact Match — SQL sinh ra khớp chính xác với ground truth |
| **EX** | Execution Accuracy — kết quả thực thi khớp với ground truth |

---

## Thực nghiệm & Ablation Study

So sánh 4 cấu hình để tách biệt đóng góp của từng thành phần:

| Cấu hình | Augmentation | Schema Linking | Mô tả |
|----------|:---:|:---:|-------|
| Baseline | ✗ | ✗ | Prompting thông thường, full schema |
| +Aug | ✓ | ✗ | Thêm schema augmentation, full schema |
| +Link | ✗ | ✓ | Thêm schema linking, không augment |
| Full | ✓ | ✓ | Framework đầy đủ |

**Đánh giá H3:** So sánh delta tuyệt đối (Full − Baseline) giữa các kích thước model (0.5B, 1.5B, 3B, 7B) để xác minh mô hình nhỏ hưởng lợi nhiều hơn.

---

## Kỳ vọng kết quả

- Schema augmentation cải thiện độ chính xác sinh SQL, đặc biệt với câu hỏi chứa entity tiếng Việt không rõ ràng
- Schema linking giảm lỗi chọn sai bảng/cột (schema grounding errors)
- Mô hình nhỏ (0.5B, 1.5B) hưởng lợi nhiều hơn (delta lớn hơn) từ schema-aware enhancement
- Augmentation cải thiện đồng thời cả schema linking lẫn SQL generation

---

## Cấu trúc thư mục (dự kiến)

```
LSAF/
├── data/
│   ├── spider_vi/          # Vietnamese Spider dev set
│   └── bird_vi/            # Vietnamese BIRD dev set
├── augmentation/
│   ├── generate_aug.py     # Sinh alias/synonym/description bằng Qwen2.5-Instruct
│   └── augmented_schemas/  # Output JSON đã augment
├── linking/
│   └── schema_linker.py    # multilingual-e5 retrieval
├── generation/
│   └── sql_generator.py    # Qwen2.5-Coder inference
├── evaluation/
│   └── eval.py             # EM & EX metrics
├── prompts/
│   └── templates.py        # Prompt templates
└── README.md
```

---

## Môi trường

- Python 3.10+
- Transformers, sentence-transformers
- Tất cả model chạy local, không cần API key
