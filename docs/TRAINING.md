# Training & fine-tuning

Out of the box the system runs COCO-pretrained **yolo11n** with a class remap
(`configs/classes.yaml`). For real retail classes (shopping_cart, shelf,
checkout_counter, staff) fine-tune on domain data.

## 1. Get data
```bash
python scripts/download_datasets.py --list
python scripts/download_datasets.py --dataset kaggle-retail   # people in stores (YOLO format)
python scripts/download_datasets.py --dataset sku110k         # dense shelf products
```
Kaggle: `pip install kaggle`, put `kaggle.json` in `~/.kaggle/` (Windows:
`C:\Users\<you>\.kaggle\`). Label your own store footage with Label Studio / CVAT
exporting YOLO format for best results — 500–2000 images per class is usually enough
for a nano/small model.

## 2. Train with MLflow tracking
```bash
docker compose --profile full up -d mlflow
MLFLOW_TRACKING_URI=http://localhost:5000 \
python scripts/train.py --data datasets/kaggle-retail/data.yaml --epochs 30 --device cpu
```
Params, mAP metrics and `best.pt` are logged; the model is registered as
`retail-detector` in the MLflow model registry (versioned).

## 3. Version with DVC
```bash
pip install dvc
dvc init
dvc add datasets/kaggle-retail
git add datasets/kaggle-retail.dvc .dvc
dvc repro          # runs the train -> export pipeline in dvc.yaml
```

## 4. Deploy the new model
Update `.env`: `YOLO_MODEL=models/runs/train/weights/best.pt`, replace
`configs/classes.yaml` with your real class names mapped 1:1, restart
`vision-worker`. Evaluate tracking quality on MOT17 before/after if you change
detector confidence thresholds.
