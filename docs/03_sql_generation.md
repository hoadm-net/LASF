# SQL Generation

## Mục đích

Sinh câu SQL từ câu hỏi tiếng Việt và schema đã được augment + filter từ các bước trước.

---

## Models được đánh giá

| Model | Tham số | Mục tiêu |
|-------|---------|----------|
| `Qwen2.5-Coder-0.5B-Instruct` | 0.5B | Giới hạn dưới |
| `Qwen2.5-Coder-1.5B-Instruct` | 1.5B | Edge device |
| `Qwen2.5-Coder-3B-Instruct` | 3B | Cân bằng |
| `Qwen2.5-Coder-7B-Instruct` | 7B | Giới hạn trên trong scope nhỏ |

Lý do chọn Qwen2.5-Coder:
- Được fine-tune cho code/SQL generation
- Hỗ trợ instruction following tốt
- Có nhiều kích thước để so sánh theo H3

---

## Prompt format

```text
### Task
Given a SQLite database schema and a question in Vietnamese, generate the correct SQL query.
Only return the SQL query, no explanation.

### Schema
Table: student (sinh viên)
  - stu_id INTEGER | alias: mã sinh viên | values: 10001, 10002
  - gpa REAL | alias: điểm trung bình, học lực | values: 3.5, 2.8
  - dept_code TEXT | alias: mã khoa | values: CS, EE

Table: department (khoa)
  - dept_code TEXT | alias: mã khoa | values: CS, EE
  - dept_name TEXT | alias: tên khoa | values: Computer Science, Electrical Engineering

Foreign keys: student.dept_code = department.dept_code

### Question
Sinh viên nào có điểm trung bình cao nhất?

### SQL
```

---

## Tham số inference

| Tham số | Giá trị |
|---------|---------|
| `input_max_length` | 4096 tokens trong local batch inference (`truncation=True`) |
| `max_new_tokens` | 256 |
| `temperature` | 0.0 (greedy) |
| `do_sample` | False |

Dùng greedy decoding để đảm bảo reproducibility. Trong thiết lập local chạy batch, prompt đầu vào hiện bị cắt ở 4096 tokens; đây là một chi tiết quan trọng khi đánh giá trên các schema lớn như BIRD-VI.

---

## Post-processing

Sau khi model sinh ra text, cần extract SQL:

1. Lấy phần text sau `### SQL`
2. Dừng tại dấu `;` đầu tiên hoặc khi gặp newline kép
3. Loại bỏ markdown code block nếu model sinh ra (` ```sql ... ``` `)

---

## Các cấu hình thực nghiệm (Ablation)

| Cấu hình | Schema trong prompt | Augmentation |
|----------|---------------------|--------------|
| Baseline | Full schema, tên EN gốc | Không |
| +Aug | Full schema | Có (alias VI, synonym, description) |
| +Link | Top-k schema (filter) | Không |
| Full | Top-k schema (filter) | Có |

---

## Lưu ý

- Mỗi cấu hình được chạy trên **tất cả 4 kích thước model** để phục vụ đánh giá H3
- Kết quả SQL được lưu vào file JSONL để đánh giá offline
- Không dùng few-shot (zero-shot hoàn toàn, nhất quán với thiết kế training-free)
