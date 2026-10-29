# T2 — Kiểm tra metadata tiếng Việt (augmentation)

**Trạng thái:** ⏳ chưa có phiếu chấm. Cần các file `augmentation/augmented_schemas/*.json` **đã dùng trong thực nghiệm v1** (20 DB ViSpider + 11 DB ViBIRD), hiện nằm trên máy chạy cũ.

**Giao cho:** 2 người, làm độc lập · **Thời gian:** khoảng 4 giờ/người · **Hạn:** 07/11/2026

## Khi đã có file augmented schemas

```bash
python revision/scripts/make_t2_sheets.py \
  --aug_dir augmentation/augmented_schemas \
  --vispider data/spider_vi/vispider_dev.json \
  --vibird data/bird_vi/vibird_dev.json \
  --out revision/human_tasks/T2_metadata_check
```

Lệnh này sinh ra:

- `T2_metadata_annotator_A.xlsx`, `T2_metadata_annotator_B.xlsx`, mỗi file gồm:
  - sheet **Cột**: 200 cột (80 ViSpider + 120 ViBIRD), lấy mẫu theo tỉ lệ số cột của từng DB, seed 2026. Mỗi cột chấm tên tiếng Việt, từ đồng nghĩa và mô tả theo thang 1–3, cộng câu hỏi "có thể gây nhầm cột".
  - sheet **Bảng**: toàn bộ bảng (khoảng 156), chấm tên tiếng Việt theo thang 1–3.
- `coverage.csv`: tỉ lệ cột có metadata trống (khi augmentation trả về JSON lỗi). Phần này không cần người chấm.
- `sample_ids.csv`: danh sách cột được chọn.

Khi nhận lại, tính độ đồng thuận bằng `agreement.py --task t2`.
