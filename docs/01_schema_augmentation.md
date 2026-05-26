# Schema Augmentation

## Mục đích

Bước này chạy **offline, một lần duy nhất cho mỗi schema**. Mục tiêu là mở rộng schema gốc (tiếng Anh) thành một schema giàu ngữ nghĩa hơn, giúp:

1. Model schema linking dễ match câu hỏi tiếng Việt với schema tiếng Anh (VI↔VI thay vì VI↔EN)
2. Model SQL generation hiểu rõ ý nghĩa từng bảng/cột hơn khi đọc prompt

---

## Vấn đề cần giải quyết

Schema gốc trong Spider/BIRD thường có dạng:

```sql
CREATE TABLE student (
    stu_id INTEGER,
    gpa REAL,
    dept_code TEXT
);
```

Câu hỏi tiếng Việt: *"Sinh viên nào có điểm trung bình cao nhất?"*

Model nhỏ rất khó liên kết `gpa` ↔ `"điểm trung bình"` vì không có cầu nối ngữ nghĩa.

---

## Model sử dụng

**`Qwen2.5-7B-Instruct`** — chạy local, không cần API.

Lý do chọn:
- Cùng họ với SQL generation model → nhất quán
- 7B đủ mạnh để sinh alias/description chất lượng
- Offline nên không ảnh hưởng inference latency

---

## Output format

Mỗi schema được lưu dưới dạng JSON với cấu trúc:

```json
{
  "table_name": "student",
  "alias_vi": "sinh viên",
  "columns": [
    {
      "name": "stu_id",
      "type": "INTEGER",
      "alias_vi": "mã sinh viên",
      "synonym": ["id sinh viên", "mã số sinh viên"],
      "sample_values": ["10001", "10002", "10003"],
      "description": "Mã định danh duy nhất của sinh viên"
    },
    {
      "name": "gpa",
      "type": "REAL",
      "alias_vi": "điểm trung bình",
      "synonym": ["học lực", "điểm tích lũy", "GPA"],
      "sample_values": ["3.5", "2.8", "3.9"],
      "description": "Điểm trung bình tích lũy của sinh viên, thang 4.0"
    },
    {
      "name": "dept_code",
      "type": "TEXT",
      "alias_vi": "mã khoa",
      "synonym": ["khoa", "bộ môn"],
      "sample_values": ["CS", "EE", "BA"],
      "description": "Mã viết tắt của khoa mà sinh viên thuộc về"
    }
  ]
}
```

---

## Prompt template

Prompt gửi cho `Qwen2.5-7B-Instruct` để sinh augmentation:

```text
You are a bilingual database expert. Given a SQL table schema, generate Vietnamese metadata for each table and column.

For each table, provide:
- alias_vi: Vietnamese name of the table

For each column, provide:
- alias_vi: Vietnamese name of the column
- synonym: list of Vietnamese synonyms (2-4 items)
- description: one-sentence Vietnamese description of the column's meaning

Return a valid JSON object following this exact structure: { ... }

Schema:
CREATE TABLE student (
    stu_id INTEGER,
    gpa REAL,
    dept_code TEXT
);

Sample values:
- stu_id: 10001, 10002, 10003
- gpa: 3.5, 2.8, 3.9
- dept_code: CS, EE, BA
```

---

## Lưu ý triển khai

- Sample values được trích xuất trực tiếp từ database trước khi gọi LLM
- Output JSON được validate bằng Pydantic schema trước khi lưu
- Nếu LLM sinh JSON lỗi, retry tối đa 3 lần với temperature thấp hơn
- Lưu toàn bộ augmented schemas vào `augmentation/augmented_schemas/`
