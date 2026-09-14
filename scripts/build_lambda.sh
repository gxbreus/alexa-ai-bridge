#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/lambda"
DIST_DIR="$ROOT_DIR/dist"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"
rm -f "$DIST_DIR/alexa-ai-bridge.zip"
python3 -m pip install --quiet --disable-pip-version-check --target "$BUILD_DIR" -r "$ROOT_DIR/requirements.txt"
cp -R "$ROOT_DIR/src" "$BUILD_DIR/src"
find "$BUILD_DIR" -type d \( -name '__pycache__' -o -name '*.egg-info' \) -prune -exec rm -rf {} +
find "$BUILD_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
(cd "$BUILD_DIR" && zip -qr "$DIST_DIR/alexa-ai-bridge.zip" .)
echo "Built $DIST_DIR/alexa-ai-bridge.zip"
