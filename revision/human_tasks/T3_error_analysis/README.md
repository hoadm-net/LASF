# T3 — Xem tay mẫu lỗi

**Trạng thái:** ⏳ chờ kết quả chạy lại (E1, E2) và bước phân loại lỗi tự động (A3). Dự kiến giao khoảng 07/11/2026, hạn 10/11/2026.

**Giao cho:** 2 người đọc được SQL · **Thời gian dự kiến:** khoảng 3 giờ/người

## Dự kiến nội dung

- Khoảng 120 câu mà mô hình trả lời sai, lấy theo các nhóm cần giải thích trong bài:
  - ViBIRD: `baseline` đúng nhưng `full` sai (model 7B);
  - ViSpider: `full` đúng nhưng `baseline` sai (model 0.5B);
  - một số câu sai ở mọi config.
- Mỗi câu hiển thị: câu hỏi tiếng Việt, evidence, phần schema mô hình nhận được, SQL mô hình sinh, SQL tham chiếu, và nhãn lỗi tự động.
- Người chấm xác nhận hoặc sửa nhãn lỗi (danh mục: SQL không chạy được / thiếu bảng cần thiết trong schema / chọn sai bảng / sai cột / sai điều kiện hoặc giá trị / sai hàm gộp hoặc GROUP BY / sai sắp xếp hoặc LIMIT / khác), và đánh dấu các câu nên dùng làm ví dụ trong bài.

Phiếu chấm sẽ được thêm vào thư mục này khi sẵn sàng.
