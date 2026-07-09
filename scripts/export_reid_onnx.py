"""Export osnet_x0_25 (torchreid) to ONNX for the Re-ID worker.

One-time, offline step - NOT part of any runtime requirements.txt (see
docs/REID.md). Install the export-only dependency manually before running
this script:

    pip install torchreid

torchreid pulls in its own torch/torchvision; if that conflicts with the CPU
wheels pinned in vision/requirements.txt, run this in a separate venv - only
the resulting .onnx file needs to reach the vision worker, and it gets there
via the existing `./models:/app/models` volume mount in docker-compose.yml
(no Dockerfile change, no build-time network dependency).

Use torch<2.6 (e.g. 2.1.2) in that export-only venv/container. This is a
confirmed hard requirement, not just caution: torch 2.6 flipped
`torch.load`'s `weights_only` default to True, and torchreid's
`load_pretrained_weights` was never patched for it - loading the
pretrained checkpoint raises "Unsupported global: GLOBAL
numpy._core.multiarray.scalar was not an allowed global by default"
(open, unresolved: https://github.com/KaiyangZhou/deep-person-reid/issues/592).
This is isolated to this one throwaway export environment - it has no
effect on the vision worker image, which stays on torch==2.6.0 in
vision/requirements.txt (the CVE-2025-32434 fix) untouched, since only the
exported .onnx file crosses that boundary.

Usage:
    python scripts/export_reid_onnx.py
    python scripts/export_reid_onnx.py --out models/reid/osnet_x0_25.onnx
"""

import argparse
from pathlib import Path

INPUT_HEIGHT, INPUT_WIDTH = 256, 128  # OSNet's expected person-crop size
EXPECTED_EMBEDDING_DIM = 512  # vision/reid.py and the /ingest/reid schema both assume this


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="models/reid/osnet_x0_25.onnx")
    parser.add_argument(
        "--model-name",
        default="osnet_x0_25",
        help="any torchreid model name - osnet_x0_25 is the lightest OSNet width variant",
    )
    args = parser.parse_args()

    import torch
    import torchreid

    model = torchreid.models.build_model(
        name=args.model_name,
        # discarded - eval-mode OSNet.forward() returns pooled features, not logits
        num_classes=1000,
        pretrained=True,
    )
    model.eval()

    dummy_input = torch.randn(1, 3, INPUT_HEIGHT, INPUT_WIDTH)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    torch.onnx.export(
        model,
        dummy_input,
        str(out_path),
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
        opset_version=17,
    )

    with torch.no_grad():
        actual_dim = model(dummy_input).shape[-1]
    print(f"Re-ID ONNX exported: {out_path}")
    if actual_dim != EXPECTED_EMBEDDING_DIM:
        print(
            f"WARNING: output dim is {actual_dim}, but vision/reid.py and the "
            f"/ingest/reid schema both assume {EXPECTED_EMBEDDING_DIM} - update "
            "both before deploying this export."
        )


if __name__ == "__main__":
    main()
