"""
Inter-annotator agreement for the T1/T2/T3 annotation workbooks.

Reports, per rating column: number of paired ratings, raw agreement, Cohen's kappa,
and linearly weighted kappa for ordinal (1-3) scales. Also writes the rows where the
two annotators disagree, for adjudication.

Usage:
    python revision/scripts/agreement.py --task t1 \
        --a T1_translation_annotator_A.xlsx --b T1_translation_annotator_B.xlsx \
        --out evaluation/analysis_v2/agreement_t1
"""

import argparse
from pathlib import Path

import pandas as pd

TASKS = {
    "t1": {
        "ViSpider": {"Độ chính xác nghĩa (1–3)": "ordinal", "Độ tự nhiên (1–3)": "ordinal",
                     "Lỗi ảnh hưởng SQL?": "nominal", "Loại lỗi": "nominal"},
        "ViBIRD": {"Độ chính xác nghĩa (1–3)": "ordinal", "Độ tự nhiên (1–3)": "ordinal",
                   "Lỗi ảnh hưởng SQL?": "nominal", "Loại lỗi": "nominal",
                   "Độ chính xác evidence (1–3)": "ordinal"},
    },
    "t2": {
        "Cột": {"Tên tiếng Việt (1–3)": "ordinal", "Từ đồng nghĩa (1–3)": "ordinal",
                "Mô tả (1–3)": "ordinal", "Có thể gây nhầm cột?": "nominal"},
        "Bảng": {"Tên tiếng Việt (1–3)": "ordinal"},
    },
    "t3": {
        "Lỗi": {"Nhãn lỗi đúng": "nominal", "Câu hỏi/SQL tham chiếu có vấn đề?": "nominal",
                "Dùng làm ví dụ trong bài?": "nominal"},
    },
}
KEY = "STT"


def cohen_kappa(a, b, labels, weighted=False):
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    n = len(a)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    row = [sum(obs[i]) for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i, j):
        if weighted:
            return abs(i - j) / (k - 1) if k > 1 else 0.0
        return 0.0 if i == j else 1.0

    d_obs = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    d_exp = sum(w(i, j) * row[i] * col[j] for i in range(k) for j in range(k)) / (n * n)
    return 1.0 if d_exp == 0 else 1 - d_obs / d_exp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=TASKS, required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary, disagreements = [], []
    for sheet, cols in TASKS[args.task].items():
        da = pd.read_excel(args.a, sheet_name=sheet).set_index(KEY)
        db = pd.read_excel(args.b, sheet_name=sheet).set_index(KEY)
        for col, kind in cols.items():
            pair = pd.DataFrame({"a": da[col], "b": db[col]}).dropna()
            if pair.empty:
                continue
            a, b = pair["a"].tolist(), pair["b"].tolist()
            if kind == "ordinal":
                labels = sorted(set(a) | set(b))
            else:
                labels = sorted(set(map(str, a)) | set(map(str, b)))
                a, b = list(map(str, a)), list(map(str, b))
            summary.append({
                "sheet": sheet, "column": col, "n": len(a),
                "agreement": sum(x == y for x, y in zip(a, b)) / len(a),
                "kappa": cohen_kappa(a, b, labels),
                "weighted_kappa": cohen_kappa(a, b, labels, weighted=True) if kind == "ordinal" else None,
                "mean_a": pair["a"].mean() if kind == "ordinal" else None,
                "mean_b": pair["b"].mean() if kind == "ordinal" else None,
            })
            for stt, row in pair[pair["a"].astype(str) != pair["b"].astype(str)].iterrows():
                disagreements.append({"sheet": sheet, KEY: stt, "column": col, "a": row["a"], "b": row["b"]})

    pd.DataFrame(summary).to_csv(out / "agreement_summary.csv", index=False)
    pd.DataFrame(disagreements).to_csv(out / "disagreements.csv", index=False)
    print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    main()
