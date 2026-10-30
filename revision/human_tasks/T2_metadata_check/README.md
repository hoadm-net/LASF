# T2 — Kiểm tra metadata tiếng Việt (augmentation)

**Trạng thái:** ✅ Sẵn sàng · **Hạn nộp:** 07/11/2026

**Giao cho:** 2 người, làm độc lập · **Thời gian dự kiến:** khoảng 4 giờ/người

## File

- `T2_metadata_annotator_A.xlsx`, `T2_metadata_annotator_B.xlsx`: hai bản giống nhau, mỗi người một bản.
- `sample_ids.csv`: danh sách cột được chọn (không cần gửi cho người chấm).
- `coverage.csv`: số cột có metadata trống theo từng DB (máy tính, không cần người chấm). ViSpider 439/439 cột có metadata; ViBIRD 796/798.

## Mỗi file gồm

| Sheet | Nội dung |
|---|---|
| Hướng dẫn | Thang điểm, quy tắc, dòng ví dụ; điền họ tên và ngày |
| Cột | 200 cột (80 ViSpider + 120 ViBIRD), lấy mẫu theo tỉ lệ số cột của từng DB, seed 2026. Mỗi cột hiển thị tên bảng/cột gốc, kiểu, giá trị mẫu và metadata tiếng Việt do mô hình sinh |
| Bảng | Toàn bộ 155 bảng của hai bộ dữ liệu |
| Danh mục | Danh sách giá trị cho ô chọn (không sửa) |

## Tiêu chí chấm (tóm tắt)

| Tiêu chí | Thang |
|---|---|
| Tên tiếng Việt (cột và bảng) | 3 đúng nghĩa, cách người Việt thường gọi · 2 đúng nghĩa nhưng chưa tự nhiên hoặc quá chung/hẹp · 1 sai nghĩa hoặc trống |
| Từ đồng nghĩa | 3 tất cả phù hợp · 2 có ít nhất một từ không phù hợp · 1 phần lớn không phù hợp hoặc trống |
| Mô tả | 3 đúng nội dung cột · 2 đúng một phần, mơ hồ hoặc có chi tiết bịa · 1 sai hoặc trống |
| Có thể gây nhầm cột? | Có / Không: metadata có thể khiến người hoặc mô hình nhầm sang cột khác trong cùng database |

Chi tiết đầy đủ nằm trong sheet "Hướng dẫn". Metadata được sinh bằng `augmentation/generate_aug.py` (Qwen2.5-7B-Instruct, seed 2026); phiếu sinh bằng `revision/scripts/make_t2_sheets.py`.

## Sau khi nhận lại

```bash
python revision/scripts/agreement.py --task t2 \
  --a revision/human_tasks/T2_metadata_check/T2_metadata_annotator_A.xlsx \
  --b revision/human_tasks/T2_metadata_check/T2_metadata_annotator_B.xlsx \
  --out evaluation/analysis_v2/agreement_t2
```
