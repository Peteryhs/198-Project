#!/usr/bin/env bash
# Fetch the PHYTMO upper-limb recordings and lay them out where the scripts expect.
#
#   ./scripts/fetch_data.sh [target-dir]     default target: ./data
#
# Downloads 3.4 GB from Zenodo and extracts only inertial/upper (598 MB, 1,484 CSV files).
# Re-running is safe: wget resumes, unzip overwrites.
set -euo pipefail

TARGET="${1:-./data}"
ZIP="PHYTMO.zip"
URL="https://zenodo.org/api/records/6319979/files/PHYTMO.zip/content"
EXPECTED_BYTES=3694420037

mkdir -p "$TARGET"

if [ ! -f "$ZIP" ] || [ "$(stat -c%s "$ZIP" 2>/dev/null || echo 0)" -lt "$EXPECTED_BYTES" ]; then
  echo "downloading PHYTMO.zip (3.4 GB) — this resumes if interrupted"
  wget -c -O "$ZIP" "$URL"
fi

have=$(stat -c%s "$ZIP")
if [ "$have" -ne "$EXPECTED_BYTES" ]; then
  echo "ERROR: $ZIP is $have bytes, expected $EXPECTED_BYTES" >&2
  exit 1
fi

echo "extracting inertial/upper only"
unzip -o -q "$ZIP" 'inertial/upper/*' -d "$TARGET"

n=$(find "$TARGET/inertial/upper" -name '*.csv' | wc -l)
echo "done: $n CSV files under $TARGET/inertial/upper"
echo
echo "expected: 1484 files, of which 1368 carry a correct/wrong label"
echo "the scripts take --root, so point them at $TARGET/inertial/upper"
