#!/bin/sh
# Split a side-by-side before/after screenshot and diff the two halves.
#
# Usage: diffcmp.sh IN.png [left-w] [gap] [out-prefix]
#   IN.png       full-width comparison image (default: colltint-compare.png)
#   left-w       width of the left half in px (default: half the image width)
#   gap          x offset of the right half from the left half (default: 0)
#   out-prefix   prefix for left/right/diffmap outputs (default: /tmp/diffcmp)
#
# Prints: changed-pixel count (ImageMagick compare -metric AE, fuzz 3%)
# and the mean of the difference map (0 = identical).
set -e

IN="${1:-/tmp/colltint-compare.png}"
PREFIX="${4:-/tmp/diffcmp}"
W=$(magick "$IN" -format "%w" info:)
LW="${2:-$((W / 2))}"
GAP="${3:-0}"

magick "$IN" -crop "${LW}x+0+0" +repage "${PREFIX}-left.png"
magick "$IN" -crop "${LW}x+$((LW + GAP))+0" +repage "${PREFIX}-right.png"
echo "changed pixels (fuzz 3%):"
compare -metric AE -fuzz 3% "${PREFIX}-left.png" "${PREFIX}-right.png" null: 2>&1 | head -1
echo
magick "${PREFIX}-left.png" "${PREFIX}-right.png" -compose difference -composite -threshold 5% "${PREFIX}-diffmap.png"
magick "${PREFIX}-diffmap.png" -format "diffmap mean: %[fx:mean]\n" info:
