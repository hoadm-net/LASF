"""
scripts/download_data.py — Download datasets and databases.

Usage:
    python scripts/download_data.py --all
    python scripts/download_data.py --dataset spider_vi
    python scripts/download_data.py --dataset bird_vi
    python scripts/download_data.py --db only
"""

import argparse
import json
import zipfile
from pathlib import Path

import gdown
from datasets import load_dataset

# Google Drive file ID for the database zip
DB_GDRIVE_ID = "1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J"

HF_DATASETS = {
    "spider_vi": "hoadm/vispider",
    "bird_vi":   "hoadm/vibird",
}

DATA_DIRS = {
    "spider_vi": "data/spider_vi",
    "bird_vi":   "data/bird_vi",
}


def download_hf_dataset(name: str, hf_repo: str, out_dir: str) -> None:
    from huggingface_hub import HfApi, hf_hub_download

    print(f"\n[HuggingFace] Downloading {hf_repo} → {out_dir}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    api = HfApi()
    all_files = list(api.list_repo_files(hf_repo, repo_type="dataset"))

    # Find dev and train JSON files — prefer files containing 'dev'/'train' in name
    def pick_file(keyword: str) -> str | None:
        # Priority: exact match "dev.json", then anything with keyword in name
        exact = f"{keyword}.json"
        if exact in all_files:
            return exact
        candidates = [f for f in all_files if keyword in f.lower() and f.endswith(".json")]
        # Prefer shorter names (less likely to be a variant)
        return sorted(candidates, key=len)[0] if candidates else None

    splits = {"dev": pick_file("dev"), "train": pick_file("train")}

    for split, filename in splits.items():
        if filename is None:
            print(f"  [{split}] No matching file found, skipping.")
            continue
        out_path = Path(out_dir) / f"{split}.json"
        if out_path.exists():
            print(f"  [{split}] Already exists, skipping.")
            continue
        print(f"  [{split}] Downloading '{filename}' ...")
        local = hf_hub_download(repo_id=hf_repo, filename=filename, repo_type="dataset")
        with open(local, encoding="utf-8") as f:
            data = json.load(f)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [{split}] Saved {len(data)} examples → {out_path}")


def download_databases(out_dir: str = "data") -> None:
    print(f"\n[Google Drive] Downloading database zip → {out_dir}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    zip_path = Path(out_dir) / "databases.zip"
    if not zip_path.exists():
        url = f"https://drive.google.com/uc?id={DB_GDRIVE_ID}"
        gdown.download(url, str(zip_path), quiet=False)
    else:
        print(f"  databases.zip already exists, skipping download.")

    print(f"  Extracting {zip_path} → {out_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(out_dir)
    print(f"  Extraction complete.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Download everything")
    group.add_argument("--dataset", choices=["spider_vi", "bird_vi"], help="Download specific dataset only")
    group.add_argument("--db", action="store_true", help="Download databases only")
    args = parser.parse_args()

    if args.all or args.dataset == "spider_vi":
        download_hf_dataset("spider_vi", HF_DATASETS["spider_vi"], DATA_DIRS["spider_vi"])

    if args.all or args.dataset == "bird_vi":
        download_hf_dataset("bird_vi", HF_DATASETS["bird_vi"], DATA_DIRS["bird_vi"])

    if args.all or args.db:
        download_databases()

    print("\nDone.")


if __name__ == "__main__":
    main()
