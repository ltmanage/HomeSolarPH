#!/usr/bin/env bash
# Fails if requirements.txt (used by Vercel) is out of step with uv.lock.
set -euo pipefail
tmp=$(mktemp)
uv export --no-dev --no-hashes --format requirements-txt -q -o "$tmp"
sed -i '/^-e \./d' "$tmp"
if ! diff -q <(grep -v '^#' "$tmp") <(grep -v '^#' requirements.txt | tr -d '\r') >/dev/null; then
  echo "requirements.txt is out of date. Run:"
  echo "  uv export --no-dev --no-hashes --format requirements-txt -o requirements.txt && sed -i '/^-e \./d' requirements.txt"
  diff <(grep -v '^#' "$tmp") <(grep -v '^#' requirements.txt | tr -d '\r') || true
  exit 1
fi
echo "requirements.txt matches uv.lock"
