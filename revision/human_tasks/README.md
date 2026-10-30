# Việc cần người thực hiện — bản sửa JICT

Thư mục này chứa các phiếu chấm cần giao cho người làm. Mỗi việc có **hai bản giống hệt nhau cho hai người chấm (A và B)**. Hai người làm **độc lập**, không trao đổi kết quả với nhau cho đến khi cả hai đã nộp.

| Việc | Nội dung | Trạng thái | Giao | Hạn nộp lại |
|---|---|---|---|---|
| **T1** | Chất lượng bản dịch câu hỏi và evidence (100 câu ViSpider + 100 câu ViBIRD) | ✅ Sẵn sàng | 30/10/2026 | **05/11/2026** |
| **T2** | Chất lượng metadata tiếng Việt do mô hình sinh (200 cột + toàn bộ bảng) | ✅ Sẵn sàng | 30/10/2026 | **07/11/2026** |
| **T3** | Xem tay mẫu lỗi của mô hình (120 câu) | ✅ Sẵn sàng | 30/10/2026 | **10/11/2026** |

## Danh sách file

```
human_tasks/
├── README.md                          (file này)
├── annotator_info.xlsx                phiếu thông tin người chấm — người phụ trách điền
├── T1_translation_check/
│   ├── README.md
│   ├── T1_translation_annotator_A.xlsx    gửi người chấm A
│   ├── T1_translation_annotator_B.xlsx    gửi người chấm B
│   └── sample_ids.csv                     danh sách câu (giữ lại, không cần gửi)
├── T2_metadata_check/
│   ├── README.md
│   ├── T2_metadata_annotator_A.xlsx
│   ├── T2_metadata_annotator_B.xlsx
│   ├── sample_ids.csv
│   └── coverage.csv                       số liệu máy tính, không cần người chấm
└── T3_error_analysis/
    ├── README.md
    ├── T3_error_annotator_A.xlsx
    ├── T3_error_annotator_B.xlsx
    └── sample_ids.csv
```

Mỗi người chấm chỉ cần nhận **một file .xlsx** của việc mình làm (bản A hoặc B). Các file `.csv` và `README.md` để người phụ trách giữ lại.

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

Script tính độ đồng thuận (Cohen's κ) và xuất `disagreements.csv` gồm các câu hai người chấm khác nhau. Sau đó một người thứ ba (hoặc hai người cùng ngồi lại) quyết định điểm cuối cho các câu này. Lệnh cho T2 và T3 nằm trong README của từng thư mục (`--task t2`, `--task t3`).

## Thông tin cho bài báo (người phụ trách ghi lại)

Với mỗi người chấm, ghi vào `annotator_info.xlsx`: trình độ, chuyên môn, mức độ thông thạo tiếng Anh, có tham gia dịch bộ dữ liệu hay không. Reviewer có thể hỏi, và người chấm không nên là người đã dịch bộ dữ liệu.
