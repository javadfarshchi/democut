#!/usr/bin/env bash
# Download the Kokoro-82M voice (Apache-2.0 weights) as ONNX files from the kokoro-onnx GitHub release.
# ~120 MB, once. Override the folder with DEMOCUT_KOKORO_DIR.
set -euo pipefail
DIR="${DEMOCUT_KOKORO_DIR:-$HOME/.cache/democut/kokoro}"
BASE=https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0
mkdir -p "$DIR"
for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  if [ -s "$DIR/$f" ]; then echo "have $DIR/$f"; continue; fi
  echo "downloading $f ..."
  curl -fL --retry 3 -o "$DIR/$f.part" "$BASE/$f" && mv "$DIR/$f.part" "$DIR/$f"
done
echo "Kokoro voice ready in $DIR"
