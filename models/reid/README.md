# models/reid/

Not checked in (see `.gitignore`) - this directory holds the exported
Re-ID ONNX model. The vision worker picks it up through the existing
`./models:/app/models` volume mount in `docker-compose.yml`, so there's no
Dockerfile change and no build-time network dependency to produce it (see
`docs/REID.md`'s "why not the Dockerfile" note).

Produce it once (or whenever you update the model):

```bash
pip install torchreid   # offline-only export dependency, not in any requirements.txt
python scripts/export_reid_onnx.py
```

This writes `osnet_x0_25.onnx` here (override the path/filename with
`REID_MODEL_PATH` if you rename it). If the file is absent, Re-ID extraction
is disabled and the rest of the pipeline is unaffected -
`vision.reid.ReidExtractor` fails soft by design; no embeddings are produced,
so the matcher (`backend/app/services/reid_matcher.py`) simply never gets
anything to match.
