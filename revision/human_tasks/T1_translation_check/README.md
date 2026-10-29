# T1 — Kiểm tra chất lượng bản dịch ViSpider / ViBIRD

**Giao cho:** 2 người, làm độc lập · **Thời gian:** khoảng 3–4 giờ/người · **Hạn:** 05/11/2026

## Nội dung

- `T1_translation_annotator_A.xlsx`, `T1_translation_annotator_B.xlsx`: hai bản giống nhau, mỗi người chấm một bản.
- `sample_ids.csv`: danh sách câu được chọn. Mẫu ngẫu nhiên phân tầng với seed 2026: ViSpider phân tầng theo loại SQL (`sql_class`), ViBIRD phân tầng theo độ khó (`difficulty`). Sinh bằng `revision/scripts/make_t1_sheets.py`.

## Mỗi file gồm

| Sheet | Nội dung |
|---|---|
| Hướng dẫn | Thang điểm, quy tắc, dòng ví dụ; điền họ tên và ngày |
| Tổng hợp | Tự động tính tiến độ và điểm trung bình |
| ViSpider | 100 câu: câu gốc tiếng Anh, bản dịch, SQL tham chiếu |
| ViBIRD | 100 câu: như trên, thêm evidence gốc và evidence dịch |
| Danh mục | Danh sách giá trị cho ô chọn (không sửa) |

## Tiêu chí chấm (tóm tắt)

| Tiêu chí | Thang |
|---|---|
| Độ chính xác nghĩa | 3 đúng đủ · 2 sai nhỏ, không đổi SQL · 1 sai làm SQL phải khác |
| Độ tự nhiên | 3 tự nhiên · 2 cứng, mang dấu dịch máy · 1 khó hiểu |
| Lỗi ảnh hưởng SQL? | Có / Không |
| Loại lỗi | Chọn trong danh sách |
| Độ chính xác evidence (ViBIRD) | 3 / 2 / 1, để trống nếu evidence gốc trống |

Chi tiết đầy đủ nằm trong sheet "Hướng dẫn".
