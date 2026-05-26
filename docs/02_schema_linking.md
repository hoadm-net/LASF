# Schema Linking

## Mục đích

Câu hỏi tiếng Việt thường chỉ liên quan đến một phần nhỏ schema. Việc đưa toàn bộ schema vào prompt gây ra hai vấn đề:

1. **Context noise:** model bị nhiễu bởi các bảng/cột không liên quan
2. **Context length:** schema lớn (BIRD có thể có 20+ bảng) vượt quá khả năng xử lý hiệu quả của model nhỏ

Schema linking chọn ra **top-k tables/columns liên quan nhất** trước khi đưa vào prompt SQL generation.

---

## Model sử dụng

**`intfloat/multilingual-e5-large`** — embedding model đa ngôn ngữ.

Lý do chọn:
- Hỗ trợ tốt cả tiếng Việt lẫn tiếng Anh
- Nhỏ và nhanh, phù hợp với mục tiêu "lightweight"
- Không cần fine-tune, sử dụng trực tiếp

Phương án nhẹ hơn: `intfloat/multilingual-e5-base`

---

## Cơ chế hoạt động

```text
Câu hỏi tiếng Việt
        │  embed
        ▼
  Question vector (768-dim)
        │
        │  cosine similarity
        ▼
  Column vectors (768-dim each)   ← embed từ augmented schema (alias VI + tên EN)
        │
        ▼
  Ranked list of columns
        │
        ▼
  Top-k columns → group by table → retrieved schema
```

---

## Đơn vị retrieval

Retrieval ở mức **column-level** (không phải table-level).

Mỗi document trong index đại diện cho một column, với text được build từ augmented schema:

```text
[Table: student | sinh viên]
Column: gpa (điểm trung bình, học lực, điểm tích lũy)
Description: Điểm trung bình tích lũy của sinh viên, thang 4.0
Sample values: 3.5, 2.8, 3.9
```

Sau khi chọn top-k columns, **giữ nguyên toàn bộ bảng** chứa ít nhất một column được chọn để tránh mất foreign key context.

---

## Tham số

| Tham số | Giá trị mặc định | Mô tả |
|---------|-----------------|-------|
| `top_k` | 10 | Số columns lấy ra |
| `min_tables` | 1 | Số bảng tối thiểu giữ lại |
| `always_include_pk` | True | Luôn giữ primary key của bảng được chọn |

---

## Lợi ích của schema augmentation với schema linking

Vì augmentation đã sinh alias tiếng Việt, embedding có thể match:

- Câu hỏi: *"điểm trung bình"* ↔ Column text: *"gpa (điểm trung bình, học lực)"*

Thay vì phải match cross-lingual:

- Câu hỏi: *"điểm trung bình"* ↔ Column text: *"gpa"*  ← khó hơn nhiều

Đây là lý do augmentation cải thiện **cả hai** schema linking và SQL generation.

---

## Output

Một dict chứa schema đã được filter, dùng làm input cho bước SQL generation:

```python
{
    "tables": [
        {
            "name": "student",
            "alias_vi": "sinh viên",
            "columns": [
                # chỉ các columns được retrieve, kèm augmented info
            ]
        }
    ]
}
```
