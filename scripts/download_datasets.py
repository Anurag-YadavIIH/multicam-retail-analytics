"""Dataset fetcher for training / evaluation.

Public direct downloads:  MOT17, MOT20, SKU-110K (via mirrors), CrowdHuman links.
Kaggle datasets:          uses the `kaggle` CLI - set KAGGLE_USERNAME/KAGGLE_KEY
                          (kaggle.com -> Account -> Create API Token).

Usage:
  python scripts/download_datasets.py --dataset mot17
  python scripts/download_datasets.py --dataset sku110k
  python scripts/download_datasets.py --dataset kaggle-retail    # Kaggle CLI required
  python scripts/download_datasets.py --list
"""

import argparse
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path("datasets")

DIRECT = {
    "mot17": {
        "url": "https://motchallenge.net/data/MOT17.zip",
        "note": "Multi-object tracking benchmark (~5GB). Used to validate ByteTrack settings.",
    },
    "mot20": {
        "url": "https://motchallenge.net/data/MOT20.zip",
        "note": "Crowded-scene tracking (~5GB).",
    },
    "sku110k": {
        "url": "http://trax-geometry.s3.amazonaws.com/cvpr_challenge/SKU110K_fixed.tar.gz",
        "note": "Dense retail shelf products (~13GB). For shelf/product fine-tuning.",
    },
}

KAGGLE = {
    "kaggle-retail": {
        "slug": "hectorlopezhernandez/retail-store-people-detection",  # people in retail stores
        "note": "Retail store people detection images (YOLO format).",
    },
    "kaggle-rpc": {
        "slug": "diyer22/retail-product-checkout-dataset",
        "note": "Retail Product Checkout (RPC) - checkout product recognition.",
    },
}

MANUAL = """
Manual-download datasets (license requires acceptance on the site):
  CrowdHuman : https://www.crowdhuman.org/download.html  -> datasets/crowdhuman/
  VisDrone   : https://github.com/VisDrone/VisDrone-Dataset -> datasets/visdrone/
  Open Images: https://storage.googleapis.com/openimages/web/download_v7.html
  COCO 2017  : https://cocodataset.org/#download (or `pip install fiftyone` loaders)
"""


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"exists: {dest}")
        return
    print(f"downloading {url}\n      -> {dest}  (this can be large)")
    urllib.request.urlretrieve(url, dest)  # noqa: S310
    if dest.suffix == ".zip":
        with zipfile.ZipFile(dest) as z:
            z.extractall(dest.parent)


def kaggle_download(slug: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["kaggle", "datasets", "download", "-d", slug, "-p", str(dest), "--unzip"]
    print("running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=[*DIRECT, *KAGGLE])
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list or not args.dataset:
        print("Direct:")
        for k, v in DIRECT.items():
            print(f"  {k:14s} {v['note']}")
        print("Kaggle (needs kaggle CLI + API token):")
        for k, v in KAGGLE.items():
            print(f"  {k:14s} {v['note']}  [{v['slug']}]")
        print(MANUAL)
        return

    if args.dataset in DIRECT:
        info = DIRECT[args.dataset]
        download(info["url"], ROOT / args.dataset / Path(info["url"]).name)
    else:
        info = KAGGLE[args.dataset]
        try:
            kaggle_download(info["slug"], ROOT / args.dataset)
        except FileNotFoundError:
            sys.exit("kaggle CLI not found: pip install kaggle, then place kaggle.json")


if __name__ == "__main__":
    main()
