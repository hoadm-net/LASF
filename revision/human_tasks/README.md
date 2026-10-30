# Việc cần người thực hiện — bản sửa JICT

Thư mục này chứa các phiếu chấm cần giao cho người làm. Mỗi việc có **hai bản giống hệt nhau cho hai người chấm (A và B)**. Hai người làm **độc lập**, không trao đổi kết quả với nhau cho đến khi cả hai đã nộp.

| Việc | Nội dung | Trạng thái | Giao | Hạn nộp lại |
|---|---|---|---|---|
| **T1** | Chất lượng bản dịch câu hỏi và evidence (100 câu ViSpider + 100 câu ViBIRD) | ✅ Sẵn sàng | 30/10/2026 | **05/11/2026** |
| **T2** | Chất lượng metadata tiếng Việt do mô hình sinh (200 cột + toàn bộ bảng) | ✅ Sẵn sàng | 30/10/2026 | **07/11/2026** |
| **T3** | Xem tay mẫu lỗi của mô hình (120 câu) | ✅ Sẵn sàng | 30/10/2026 | **10/11/2026** |

## Yêu cầu với người chấm

- Thông thạo tiếng Việt và tiếng Anh. Với T2 và T3 cần đọc được SQL cơ bản (SELECT, WHERE, JOIN, GROUP BY).
- Mở bằng Microsoft Excel hoặc Google Sheets (File → Import, giữ nguyên định dạng).
- Mỗi file có sheet **"Hướng dẫn"** giải thích thang điểm và có một dòng ví dụ. Đọc kỹ trước khi chấm.
- Chỉ điền vào các ô **nền vàng**. Các ô nền xám là dữ liệu, không sửa. Không thêm, xóa hoặc sắp xếp lại dòng.
- Điền họ tên và ngày hoàn thành ở sheet "Hướng dẫn".

## Nộp lại

Gửi lại file `.xlsx` **giữ nguyên tên**, ví dụ `T1_translation_annotator_A.xlsx`. Người phụ trách chép file vào đúng thư mục này rồi chạy:

```bash
python revision/scripts/agreement.py --task t1 \
  --a revision/human_tasks/T1_translation_check/T1_translation_annotator_A.xlsx \
  --b revision/human_tasks/T1_translation_check/T1_translation_annotator_B.xlsx \
  --out evaluation/analysis_v2/agreement_t1
```

Script tính độ đồng thuận (Cohen's κ) và xuất `disagreements.csv` gồm các câu hai người chấm khác nhau. Sau đó một người thứ ba (hoặc hai người cùng ngồi lại) quyết định điểm cuối cho các câu này.

## Thông tin cho bài báo (người phụ trách ghi lại)

Với mỗi người chấm, ghi: trình độ, chuyên môn, mức độ thông thạo tiếng Anh, có tham gia dịch bộ dữ liệu hay không. Reviewer có thể hỏi, và người chấm không nên là người đã dịch bộ dữ liệu.
