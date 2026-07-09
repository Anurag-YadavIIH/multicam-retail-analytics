# Datasets

Nothing here is committed to git (see .gitignore). Use `python scripts/download_datasets.py --list`.

| Dataset | Use in this project | How to get |
|---|---|---|
| Intel sample retail videos ([intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos), CC BY 4.0) | Demo camera feeds (`retail_demo.mp4`, `queue_demo.mp4`) - see `docs/DEMO.md` | `python scripts/download_sample_video.py` (automatic) |
| Kaggle: retail store people detection | Fine-tune person/staff detector | `--dataset kaggle-retail` (needs Kaggle API token) |
| Kaggle: Retail Product Checkout (RPC) | Product recognition at checkout | `--dataset kaggle-rpc` |
| SKU-110K | Dense shelf product detection | `--dataset sku110k` (13 GB) |
| MOT17 / MOT20 | Validate ByteTrack config (MOTA/IDF1) | `--dataset mot17` / `--dataset mot20` |
| CrowdHuman | Crowded-store person detection | manual (accept license on site) |
| COCO / Open Images / VisDrone | Pretraining / extra classes | manual, links in the script |

Kaggle setup (Windows): `pip install kaggle`, download `kaggle.json` from your
Kaggle account page and place it at `C:\Users\<you>\.kaggle\kaggle.json`.

Data versioning: `dvc init && dvc add datasets/kaggle-retail && git add datasets/kaggle-retail.dvc`.
