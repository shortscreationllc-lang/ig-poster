#!/usr/bin/env bash
set -euo pipefail

cd "/Users/josephborroto/Downloads/instagram-api-poster"

IMAGE_URL="${IMAGE_URL:-}"
CAPTION="$(cat test-caption.txt)"
ALT_TEXT="A dark modern Shorts Creation tip graphic that says stop asking questions in your hooks and use a bold statement instead."

if [[ -z "$IMAGE_URL" ]]; then
  echo "Missing IMAGE_URL."
  echo "Upload /Users/josephborroto/Downloads/instagram-api-poster/test-hook-post.png somewhere public,"
  echo "then run:"
  echo "IMAGE_URL='https://your-direct-image-url.png' $0"
  exit 2
fi

./ig_post.py \
  --image-url "$IMAGE_URL" \
  --caption "$CAPTION" \
  --alt-text "$ALT_TEXT"
