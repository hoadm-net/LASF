# T3 — Xem tay mẫu lỗi

**Trạng thái:** ✅ Sẵn sàng · **Hạn nộp:** 10/11/2026

**Giao cho:** 2 người đọc được SQL · **Thời gian dự kiến:** khoảng 3 giờ/người

## File

- `T3_error_annotator_A.xlsx`, `T3_error_annotator_B.xlsx`: hai bản giống nhau, mỗi người một bản.
- `sample_ids.csv`: danh sách câu được chọn (dùng khi tính kết quả, không cần gửi cho người chấm).

## Nội dung

120 câu mà mô hình sinh SQL **chạy được nhưng ra kết quả sai** (SQL không chạy được đã được máy phân loại tự động nên không đưa vào):

| Nhóm | Số câu | Nội dung | SQL được xem |
|---|---|---|---|
| A | 40 | ViBIRD, Qwen2.5-Coder-7B: `baseline` đúng nhưng `full` sai | của `full` |
| B | 40 | ViSpider, Qwen2.5-Coder-0.5B: `full` đúng nhưng `baseline` sai | của `baseline` |
| C | 40 | Sai ở cả năm config, Qwen2.5-Coder-7B (20 ViSpider + 20 ViBIRD) | của `full` |

Mỗi dòng có: câu hỏi tiếng Việt, evidence, schema đúng như mô hình nhận được trong prompt, SQL mô hình sinh, SQL tham chiếu, trạng thái thực thi và nhãn lỗi do máy gán.

Người chấm điền: nhãn lỗi đúng (chọn trong danh sách), câu hỏi/SQL tham chiếu có vấn đề không, có nên dùng làm ví dụ trong bài không, và ghi chú. Sheet "Tổng hợp" tự tính tỉ lệ nhãn máy gán đúng.

## Sau khi nhận lại

```bash
python revision/scripts/agreement.py --task t3 \
  --a revision/human_tasks/T3_error_analysis/T3_error_annotator_A.xlsx \
  --b revision/human_tasks/T3_error_analysis/T3_error_annotator_B.xlsx \
  --out evaluation/analysis_v2/agreement_t3
```
