"""Fine-tune YOLO on a retail dataset with MLflow experiment tracking.

Example (after downloading a YOLO-format dataset into datasets/):
  python scripts/train.py --data datasets/kaggle-retail/data.yaml --epochs 30
"""

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="path to YOLO data.yaml")
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default=os.getenv("DEVICE", "cpu"))
    args = parser.parse_args()

    import mlflow
    from ultralytics import YOLO

    tracking = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking)
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT", "retail-analytics"))

    with mlflow.start_run(run_name=f"finetune-{args.model}"):
        mlflow.log_params(vars(args))
        model = YOLO(args.model)
        results = model.train(
            data=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            project="models/runs",
        )
        metrics = getattr(results, "results_dict", {}) or {}
        mlflow.log_metrics(
            {
                k.replace("(", "_").replace(")", ""): float(v)
                for k, v in metrics.items()
                if isinstance(v, int | float)
            }
        )
        best = "models/runs/train/weights/best.pt"
        if os.path.exists(best):
            mlflow.log_artifact(best)
            mlflow.register_model(
                f"runs:/{mlflow.active_run().info.run_id}/best.pt", "retail-detector"
            )
        print("training complete; metrics + weights logged to MLflow")


if __name__ == "__main__":
    main()
