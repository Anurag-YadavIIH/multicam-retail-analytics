"""Export the detector to ONNX (and optionally TensorRT engine on GPU hosts)."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument(
        "--tensorrt",
        action="store_true",
        help="also build a TensorRT engine (requires NVIDIA GPU + trtexec)",
    )
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    onnx_path = model.export(format="onnx", dynamic=True, simplify=True)
    print(f"ONNX exported: {onnx_path}")
    if args.tensorrt:
        engine = model.export(format="engine", half=True)
        print(f"TensorRT engine: {engine}")


if __name__ == "__main__":
    main()
