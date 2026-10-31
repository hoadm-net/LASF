"""
Summarise the adjudicated annotation workbooks (revision/human_tasks/final/*_best.xlsx).

Each criterion has columns "<c>: Annotator 1", "<c>: Annotator 2", the final value "<c>"
and its source "<c>: nguồn" (agreement / adjudicated by annotator 3 / unresolved).

Outputs (evaluation/analysis_v2/human/):
  agreement.csv     per criterion: n pairs, raw agreement, Cohen's κ, linear weighted κ
                    (ordinal 1–3 scales), Gwet's AC1 (κ is depressed when one value dominates,
                    e.g. 98% "Không"), number adjudicated / unresolved; consistency checks
  distribution.csv  distribution of final values per criterion (+ mean for 1–3 scales)
  t3_confusion.csv  automatic error category vs final human label
  t3_by_group.csv   share of automatic labels confirmed, per group (A/B/C)
  t3_examples.csv   rows both annotators flagged as usable examples

Usage:
    python revision/scripts/human_results.py
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agreement import cohen_kappa

SHEETS = {
    "T1": ("T1_translation_best.xlsx", {
        "ViSpider": {"Độ chính xác nghĩa": "ordinal", "Độ tự nhiên": "ordinal",
                     "Lỗi ảnh hưởng SQL?": "nominal", "Loại lỗi": "nominal"},
        "ViBIRD": {"Độ chính xác nghĩa": "ordinal", "Độ tự nhiên": "ordinal", "Lỗi ảnh hưởng SQL?": "nominal",
                   "Loại lỗi": "nominal", "Độ chính xác evidence": "ordinal"}}),
    "T2": ("T2_metadata_best.xlsx", {
        "Cột": {"Tên tiếng Việt": "ordinal", "Từ đồng nghĩa": "ordinal", "Mô tả": "ordinal",
                "Có thể gây nhầm cột?": "nominal"},
        "Bảng": {"Tên tiếng Việt": "ordinal"}}),
    "T3": ("T3_error_best.xlsx", {
        "Lỗi": {"Nhãn lỗi đúng": "nominal", "Câu hỏi/SQL tham chiếu có vấn đề?": "nominal",
                "Dùng làm ví dụ trong bài?": "nominal"}}),
}


def gwet_ac1(a, b, labels):
    """Gwet's AC1: agreement coefficient that is stable when one category dominates."""
    n, k = len(a), len(labels)
    pa = sum(x == y for x, y in zip(a, b)) / n
    pi = [(a.count(l) + b.count(l)) / (2 * n) for l in labels]
    pe = sum(p * (1 - p) for p in pi) / (k - 1) if k > 1 else 0.0
    return (pa - pe) / (1 - pe) if pe < 1 else 1.0


def norm(v):
    if pd.isna(v):
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return str(v).strip() if isinstance(v, str) else v


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="revision/human_tasks/final")
    ap.add_argument("--out", default="evaluation/analysis_v2/human")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    agree_rows, dist_rows = [], []
    for task, (fname, sheets) in SHEETS.items():
        for sheet, crits in sheets.items():
            df = pd.read_excel(Path(args.dir) / fname, sheet_name=sheet)
            for crit, kind in crits.items():
                a = df[f"{crit}: Annotator 1"].map(norm)
                b = df[f"{crit}: Annotator 2"].map(norm)
                final, src = df[crit].map(norm), df[f"{crit}: nguồn"].map(norm)
                both = a.notna() & b.notna()
                la, lb = a[both].tolist(), b[both].tolist()
                labels = sorted(set(la) | set(lb), key=str)
                row = {"task": task, "sheet": sheet, "criterion": crit, "n_pairs": len(la),
                       "raw_agreement": round(sum(x == y for x, y in zip(la, lb)) / len(la), 4),
                       "kappa": round(cohen_kappa(la, lb, labels), 4)}
                if kind == "ordinal":
                    row["kappa_linear_weighted"] = round(cohen_kappa(la, lb, sorted(labels), weighted=True), 4)
                else:
                    row["kappa_linear_weighted"] = ""
                row["gwet_ac1"] = round(gwet_ac1(la, lb, labels), 4)
                row["n_adjudicated"] = int((src == "Annotator 3 phân xử").sum())
                row["n_unresolved"] = int((src == "Chưa thống nhất").sum())
                # consistency: "agreement" rows must have A == B == final
                agreed = src == "Đồng thuận"
                row["n_inconsistent"] = int((agreed & ((a != b) | (final != a))).sum())
                agree_rows.append(row)

                counts = Counter(final.dropna().tolist())
                n = sum(counts.values())
                for value, c in sorted(counts.items(), key=lambda kv: str(kv[0])):
                    dist_rows.append({"task": task, "sheet": sheet, "criterion": crit, "value": value,
                                      "count": c, "share": round(c / n, 4), "n": n,
                                      "mean": round(final.dropna().astype(float).mean(), 3) if kind == "ordinal" else ""})

    write_csv(out / "agreement.csv", agree_rows)
    write_csv(out / "distribution.csv", dist_rows)

    t3 = pd.read_excel(Path(args.dir) / SHEETS["T3"][0], sheet_name="Lỗi")
    final = t3["Nhãn lỗi đúng"].map(norm)
    resolved = final.notna()
    conf = pd.crosstab(t3.loc[resolved, "Nhãn tự động"], final[resolved])
    conf.to_csv(out / "t3_confusion.csv", encoding="utf-8")
    group_rows = []
    for g, part in t3[resolved].groupby("Nhóm"):
        ok = (part["Nhãn tự động"] == part["Nhãn lỗi đúng"]).sum()
        group_rows.append({"group": g, "n": len(part), "auto_label_confirmed": int(ok),
                           "share": round(ok / len(part), 4)})
    ok = (t3.loc[resolved, "Nhãn tự động"] == final[resolved]).sum()
    group_rows.append({"group": "all", "n": int(resolved.sum()), "auto_label_confirmed": int(ok),
                       "share": round(ok / resolved.sum(), 4)})
    write_csv(out / "t3_by_group.csv", group_rows)
    ex = t3[(t3["Dùng làm ví dụ trong bài?: Annotator 1"] == "Có") & (t3["Dùng làm ví dụ trong bài?: Annotator 2"] == "Có")]
    ex[["STT", "Nhóm", "Dataset", "Model / config", "Câu hỏi", "SQL mô hình sinh", "SQL tham chiếu",
        "Nhãn lỗi đúng", "Ghi chú"]].to_csv(out / "t3_examples.csv", index=False, encoding="utf-8")

    print(pd.DataFrame(agree_rows).to_string(index=False))
    print()
    print(pd.DataFrame(group_rows).to_string(index=False))
    print(f"\nRows flagged as examples by both annotators: {len(ex)}")


if __name__ == "__main__":
    main()
