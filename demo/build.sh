#!/usr/bin/env bash
# Regenerate the demo fixture from the real pipeline and assemble the static site.
#
#   demo/build.sh                 # export fixture, write site to demo/dist
#   demo/build.sh path/to/out     # write site somewhere else (e.g. a Pages repo)
#   SKIP_EXPORT=1 demo/build.sh   # reuse the committed fixture
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/demo/dist}"
PYTHON="${PYTHON:-python}"

if [[ "${SKIP_EXPORT:-0}" != "1" ]]; then
  (cd "$ROOT" && "$PYTHON" demo/export_fixture.py)
fi

mkdir -p "$OUT/data"
cp "$ROOT/demo/site/index.html" "$ROOT/demo/site/styles.css" "$ROOT/demo/site/app.js" "$OUT/"
cp "$ROOT/demo/site/data/fixture.json" "$OUT/data/"
echo "static demo written to $OUT"
