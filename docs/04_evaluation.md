# Evaluation

## Metrics

### Exact Match (EM)

So sánh câu SQL sinh ra với ground truth SQL sau khi normalize:
- Lowercase
- Loại bỏ khoảng trắng thừa
- Chuẩn hóa alias

**Hạn chế:** Nhiều câu SQL đúng về ngữ nghĩa nhưng có cách viết khác nhau → EM thấp hơn thực tế.

### Execution Accuracy (EX)

Thực thi cả hai câu SQL trên database thực, so sánh kết quả trả về.

**Ưu điểm:** Đánh giá đúng hơn về correctness thực tế — đây là metric quan trọng hơn.

---

## Ablation Study

4 cấu hình × 4 model sizes × 2 datasets = **32 thực nghiệm**

| Cấu hình | Aug | Link | Mục tiêu kiểm định |
|----------|:---:|:----:|---------------------|
| Baseline | ✗ | ✗ | Điểm khởi đầu |
| +Aug | ✓ | ✗ | Kiểm định H1, RQ1 |
| +Link | ✗ | ✓ | Kiểm định H2, RQ2 |
| Full | ✓ | ✓ | Hiệu quả tổng hợp |

---

## Đánh giá H3 — Hiệu quả theo kích thước model

Với mỗi model size, tính delta:

$$\Delta_{EX} = EX_{Full} - EX_{Baseline}$$

Nếu H3 đúng: $\Delta_{0.5B} > \Delta_{1.5B} > \Delta_{3B} > \Delta_{7B}$

---

## Dataset & Split

| Dataset | Split | Vai trò |
|---------|-------|---------|
| Vietnamese Spider | Dev | **Primary** — validate giả thuyết (đơn giản hơn, debug nhanh) |
| Vietnamese BIRD | Dev | **Confirmation** — xác nhận lại trên benchmark khó hơn |

Chiến lược: kiểm chứng toàn bộ H1, H2, H3 trên Spider trước, sau đó confirm lại trên BIRD.

> *"We evaluate on the dev set as our approach is training-free and involves no parameter optimization on any split."*

---

## Output format

Mỗi thực nghiệm lưu ra file JSONL:

```json
{
  "question_id": "spider_dev_001",
  "question": "Sinh viên nào có điểm trung bình cao nhất?",
  "gold_sql": "SELECT name FROM student ORDER BY gpa DESC LIMIT 1",
  "pred_sql": "SELECT name FROM student ORDER BY gpa DESC LIMIT 1",
  "exact_match": 1,
  "execution_accuracy": 1,
  "config": "full",
  "model": "Qwen2.5-Coder-3B-Instruct"
}
```

---

## Kiểm định thống kê

### H1 & H2 — McNemar's Test

EX là binary outcome (đúng/sai) theo từng sample → dùng **McNemar's test** để so sánh cặp cấu hình trên cùng test set.

$$H_0: P(\text{Aug đúng, Base sai}) = P(\text{Aug sai, Base đúng})$$

Các cặp so sánh:
- `+Aug vs Baseline` → kiểm định H1
- `+Link vs Baseline` → kiểm định H2
- `Full vs Baseline` → hiệu quả tổng hợp

Ngưỡng ý nghĩa: **p < 0.05**

### H3 — Spearman's Rank Correlation

Tính $\Delta_{EX}$ cho từng model size, sau đó kiểm định tương quan monotone:

$$\rho_s(\text{rank size},\ \Delta_{EX})$$

Với rank size: 0.5B=1, 1.5B=2, 3B=3, 7B=4.

Nếu H3 đúng: $\rho_s < 0$ và có ý nghĩa thống kê → mô hình nhỏ hơn có delta lớn hơn.

---

## Cấu trúc kết quả tổng hợp

```
evaluation/results/
├── spider_vi/
│   ├── baseline_0.5b.jsonl
│   ├── baseline_1.5b.jsonl
│   ├── ...
│   ├── full_7b.jsonl
│   └── summary.csv
└── bird_vi/
    ├── ...
    └── summary.csv
```

`summary.csv` chứa EM và EX cho tất cả cấu hình × model size để dễ phân tích.
