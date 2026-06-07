#!/usr/bin/env bash
# Run the same build steps as the CD workflow (no AWS calls).
# Use this to verify zips and paths before pushing.
# Requires: Python 3.12 (python3 -m pip used for portability)

set -e
cd "$(dirname "$0")/.."
PIP="${PIP:-python3 -m pip}"

echo "=== Build pull layer ==="
rm -rf build
mkdir -p build/pull_layer/python
"$PIP" install -r garmin_pull/requirements.txt -t build/pull_layer/python
cd build/pull_layer
zip -rq ../pull_layer.zip python
cd ../..
echo "  -> build/pull_layer.zip ($(wc -c < build/pull_layer.zip) bytes)"

echo "=== Build push layer ==="
mkdir -p build/push_layer/python
"$PIP" install -r garmin_push/requirements.txt -t build/push_layer/python
cd build/push_layer
zip -rq ../push_layer.zip python
cd ../..
echo "  -> build/push_layer.zip ($(wc -c < build/push_layer.zip) bytes)"

echo "=== Build pull code zip ==="
mkdir -p build/pull_code
cp garmin_pull/pull.py build/pull_code/
if [ -d garmin_pull/python ]; then
  cp -r garmin_pull/python build/pull_code/
fi
cd build/pull_code
zip -rq ../pull_code.zip .
cd ../..
echo "  -> build/pull_code.zip ($(wc -c < build/pull_code.zip) bytes)"
echo "  Contents:"
unzip -l build/pull_code.zip

echo "=== Build push code zip ==="
rm -rf build/push_code
mkdir -p build/push_code
cp garmin_push/push.py build/push_code/
cd build/push_code
zip -rq ../push_code.zip .
cd ../..
echo "  -> build/push_code.zip ($(wc -c < build/push_code.zip) bytes)"
echo "  Contents:"
unzip -l build/push_code.zip

echo ""
echo "Done. All artifacts under build/ (no AWS calls)."
echo "To deploy with AWS CLI: configure credentials, then run the update-function-code and layer steps from the workflow."
