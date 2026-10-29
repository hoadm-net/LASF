"""
Build the translation-quality annotation workbooks (task T1).

Draws a stratified random sample from the ViSpider and ViBIRD dev sets and writes one
identical workbook per annotator, plus the list of sampled ids.

Usage:
    python revision/scripts/make_t1_sheets.py \
        --vispider data/spider_vi/vispider_dev.json \
        --vibird data/bird_vi/vibird_dev.json \
        --out revision/human_tasks/T1_translation_check
"""

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).parent))
from sheet_utils import FONT, add_list_validation, write_guide, write_header, write_lists, write_rows

SEED = 2026
N_PER_DATASET = 100
ANNOTATORS = ["A", "B"]

SCORE_LABELS = [3, 2, 1]
YES_NO = ["Có", "Không"]
ERROR_TYPES = [
    "Không có lỗi",
    "Sai nghĩa",
    "Thiếu thông tin",
    "Thêm thông tin",
    "Sai/đổi giá trị hoặc tên riêng",
    "Sai thuật ngữ",
    "Câu không tự nhiên",
    "Khác",
]


def stratified_sample(items, key, n, rng):
    """Proportional allocation per stratum, at least 2 per stratum."""
    groups = defaultdict(list)
    for it in items:
        groups[key(it)].append(it)
    total = len(items)
    alloc = {g: max(2, round(n * len(v) / total)) for g, v in groups.items()}
    # trim/pad to exactly n, adjusting the largest strata
    while sum(alloc.values()) > n:
        g = max(alloc, key=lambda k: alloc[k])
        alloc[g] -= 1
    while sum(alloc.values()) < n:
        g = max(groups, key=lambda k: len(groups[k]) - alloc[k])
        alloc[g] += 1
    picked = []
    for g in sorted(groups):
        picked.extend(rng.sample(groups[g], min(alloc[g], len(groups[g]))))
    picked.sort(key=lambda x: x["id"])
    return picked


GUIDE_LINES = [
    ("Mục đích", "Đánh giá chất lượng bản dịch tiếng Việt của câu hỏi (và evidence với ViBIRD) so với câu gốc tiếng Anh. "
                 "Kết quả dùng để báo cáo chất lượng bộ dữ liệu trong bài báo."),
    ("Cách làm", "Mỗi dòng ở sheet ViSpider và ViBIRD là một câu. Đọc câu gốc tiếng Anh, bản dịch tiếng Việt, và SQL tham chiếu "
                 "(để hiểu câu hỏi thực sự hỏi gì). Chỉ điền vào các ô NỀN VÀNG. Các ô nền xám không sửa."),
    ("", "Hai người chấm làm ĐỘC LẬP, không trao đổi kết quả với nhau cho đến khi cả hai nộp file."),
    ("Độ chính xác nghĩa (1–3)", "3 = Đúng và đủ nghĩa so với câu gốc.\n"
                                 "2 = Có sai lệch nhỏ (từ ngữ, sắc thái) nhưng KHÔNG làm thay đổi câu SQL đúng.\n"
                                 "1 = Sai nghĩa, thiếu hoặc thêm thông tin khiến câu SQL đúng phải khác đi."),
    ("Độ tự nhiên (1–3)", "3 = Câu tiếng Việt tự nhiên, giống người Việt hỏi.\n"
                          "2 = Hiểu được nhưng hơi cứng, mang dấu vết dịch máy.\n"
                          "1 = Khó hiểu hoặc sai ngữ pháp rõ rệt."),
    ("Lỗi ảnh hưởng SQL?", "Có = nếu chỉ đọc bản dịch tiếng Việt, một người viết SQL giỏi sẽ viết ra câu SQL KHÁC với SQL tham chiếu "
                           "(ví dụ: đổi giá trị lọc, mất điều kiện, sai số lượng, sai so sánh lớn/nhỏ)."),
    ("Loại lỗi", "Chọn loại lỗi chính trong danh sách. Nếu không có lỗi, chọn \"Không có lỗi\"."),
    ("Giá trị và tên riêng", "Giá trị dùng để lọc trong SQL (tên người, địa danh, mã, số) phải được giữ nguyên hoặc tương ứng rõ ràng. "
                             "Ví dụ \"Alameda\" phải còn là \"Alameda\". Nếu bị dịch hoặc đổi khiến SQL không còn khớp thì chọn "
                             "\"Sai/đổi giá trị hoặc tên riêng\" và đánh dấu Lỗi ảnh hưởng SQL = Có."),
    ("Evidence (chỉ ViBIRD)", "Chấm độ chính xác của bản dịch evidence theo cùng thang 1–3. Evidence chứa tên cột/công thức: "
                              "tên cột trong dấu ` ` phải giữ nguyên. Nếu evidence gốc trống thì để trống."),
    ("Bản dịch đề xuất", "Không bắt buộc. Chỉ ghi khi bạn chấm Độ chính xác = 1 hoặc 2."),
    ("Thời gian dự kiến", "Khoảng 1–1,5 phút mỗi câu, tổng khoảng 3–4 giờ cho 200 câu. Có thể chia nhiều buổi."),
    ("Nộp lại", "Điền họ tên và ngày ở trên, lưu file với tên giữ nguyên, gửi lại cho người phụ trách."),
]

EXAMPLE = [
    ("Câu gốc (EN)", "What is the average, minimum, and maximum age for all French singers?"),
    ("Bản dịch (VI)", "Độ tuổi trung bình, nhỏ nhất và lớn nhất của các ca sĩ người Pháp là bao nhiêu?"),
    ("Độ chính xác nghĩa", 3),
    ("Độ tự nhiên", 3),
    ("Lỗi ảnh hưởng SQL?", "Không"),
    ("Loại lỗi", "Không có lỗi"),
    ("Bản dịch đề xuất", "(để trống)"),
]


def build_workbook(label, spider_rows, bird_rows):
    wb = Workbook()
    guide = wb.active
    guide.title = "Hướng dẫn"
    write_guide(guide, "Phiếu chấm T1 — Chất lượng bản dịch ViSpider / ViBIRD", f"Người chấm {label}",
                GUIDE_LINES, EXAMPLE)

    lists_ws = wb.create_sheet("Danh mục")
    ranges = write_lists(lists_ws, {"Điểm": SCORE_LABELS, "Có/Không": YES_NO, "Loại lỗi": ERROR_TYPES})

    # ViSpider
    ws = wb.create_sheet("ViSpider")
    headers = ["STT", "ID", "DB", "Câu gốc (EN)", "Bản dịch (VI)", "SQL tham chiếu",
               "Độ chính xác nghĩa (1–3)", "Độ tự nhiên (1–3)", "Lỗi ảnh hưởng SQL?", "Loại lỗi",
               "Bản dịch đề xuất", "Ghi chú"]
    widths = [6, 18, 18, 45, 45, 45, 14, 12, 12, 24, 40, 30]
    inputs = {7, 8, 9, 10, 11, 12}
    write_header(ws, headers, widths, inputs)
    rows = [[i, e["id"], e["db_id"], e["question"], e["question_vi"], e["query"]] + [None] * 6
            for i, e in enumerate(spider_rows, start=1)]
    write_rows(ws, rows, inputs)
    n = len(rows)
    add_list_validation(ws, 7, n, ranges["Điểm"])
    add_list_validation(ws, 8, n, ranges["Điểm"])
    add_list_validation(ws, 9, n, ranges["Có/Không"])
    add_list_validation(ws, 10, n, ranges["Loại lỗi"])

    # ViBIRD
    ws = wb.create_sheet("ViBIRD")
    headers = ["STT", "ID", "DB", "Độ khó", "Câu gốc (EN)", "Bản dịch (VI)", "Evidence gốc (EN)",
               "Evidence dịch (VI)", "SQL tham chiếu", "Độ chính xác nghĩa (1–3)", "Độ tự nhiên (1–3)",
               "Lỗi ảnh hưởng SQL?", "Loại lỗi", "Độ chính xác evidence (1–3)", "Bản dịch đề xuất", "Ghi chú"]
    widths = [6, 16, 18, 11, 40, 40, 35, 35, 45, 14, 12, 12, 24, 14, 40, 30]
    inputs = {10, 11, 12, 13, 14, 15, 16}
    write_header(ws, headers, widths, inputs)
    rows = [[i, e["id"], e["db_id"], e["difficulty"], e["question"], e["question_vi"],
             e.get("evidence", ""), e.get("evidence_vi", ""), e["SQL"]] + [None] * 7
            for i, e in enumerate(bird_rows, start=1)]
    write_rows(ws, rows, inputs)
    n = len(rows)
    for col in (10, 11, 14):
        add_list_validation(ws, col, n, ranges["Điểm"])
    add_list_validation(ws, 12, n, ranges["Có/Không"])
    add_list_validation(ws, 13, n, ranges["Loại lỗi"])

    # Progress summary (formulas)
    s = wb.create_sheet("Tổng hợp", 1)
    s.column_dimensions["A"].width = 38
    s.column_dimensions["B"].width = 14
    s.column_dimensions["C"].width = 14
    s["A1"] = "Tổng hợp (tự động tính, không cần sửa)"
    s["A1"].font = Font(name=FONT, bold=True, size=12)
    s["B2"], s["C2"] = "ViSpider", "ViBIRD"
    specs = [
        ("Số câu", "=COUNTA(ViSpider!B2:B{n})", "=COUNTA(ViBIRD!B2:B{m})"),
        ("Số câu đã chấm độ chính xác", "=COUNTA(ViSpider!G2:G{n})", "=COUNTA(ViBIRD!J2:J{m})"),
        ("Độ chính xác trung bình", "=IFERROR(SUMPRODUCT(--ViSpider!G2:G{n})/B4,\"\")",
         "=IFERROR(SUMPRODUCT(--ViBIRD!J2:J{m})/C4,\"\")"),
        ("Độ tự nhiên trung bình", "=IFERROR(SUMPRODUCT(--ViSpider!H2:H{n})/COUNTA(ViSpider!H2:H{n}),\"\")",
         "=IFERROR(SUMPRODUCT(--ViBIRD!K2:K{m})/COUNTA(ViBIRD!K2:K{m}),\"\")"),
        ("Tỉ lệ câu chấm độ chính xác = 1", "=IFERROR(COUNTIF(ViSpider!G2:G{n},1)/B4,\"\")",
         "=IFERROR(COUNTIF(ViBIRD!J2:J{m},1)/C4,\"\")"),
        ("Tỉ lệ lỗi ảnh hưởng SQL", "=IFERROR(COUNTIF(ViSpider!I2:I{n},\"Có\")/COUNTA(ViSpider!I2:I{n}),\"\")",
         "=IFERROR(COUNTIF(ViBIRD!L2:L{m},\"Có\")/COUNTA(ViBIRD!L2:L{m}),\"\")"),
    ]
    n_end, m_end = len(spider_rows) + 1, len(bird_rows) + 1
    for r, (label_txt, f1, f2) in enumerate(specs, start=3):
        s.cell(row=r, column=1, value=label_txt).font = Font(name=FONT)
        s.cell(row=r, column=2, value=f1.format(n=n_end)).font = Font(name=FONT)
        s.cell(row=r, column=3, value=f2.format(m=m_end)).font = Font(name=FONT)
        if r >= 5:
            fmt = "0.00" if r in (5, 6) else "0.0%"
            s.cell(row=r, column=2).number_format = fmt
            s.cell(row=r, column=3).number_format = fmt
    for c in ("B2", "C2"):
        s[c].font = Font(name=FONT, bold=True)
    wb.calculation.fullCalcOnLoad = True
    return wb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vispider", required=True)
    ap.add_argument("--vibird", required=True)
    ap.add_argument("--out", default="revision/human_tasks/T1_translation_check")
    args = ap.parse_args()

    rng = random.Random(SEED)
    spider = json.load(open(args.vispider, encoding="utf-8"))
    bird = json.load(open(args.vibird, encoding="utf-8"))
    spider_s = stratified_sample(spider, lambda e: e["sql_class"], N_PER_DATASET, rng)
    bird_s = stratified_sample(bird, lambda e: e["difficulty"], N_PER_DATASET, rng)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "sample_ids.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "id", "db_id", "stratum"])
        for e in spider_s:
            w.writerow(["vispider", e["id"], e["db_id"], e["sql_class"]])
        for e in bird_s:
            w.writerow(["vibird", e["id"], e["db_id"], e["difficulty"]])

    for label in ANNOTATORS:
        wb = build_workbook(label, spider_s, bird_s)
        path = out / f"T1_translation_annotator_{label}.xlsx"
        wb.save(path)
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
