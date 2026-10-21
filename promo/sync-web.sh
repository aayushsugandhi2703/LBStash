#!/bin/zsh
# Copies the film and its poster from media/ into the site's public folder (frontend/public/promo/).
set -euo pipefail
cd "$(dirname "$0")"
D=../frontend/public/promo
rm -rf $D; mkdir -p $D/videos $D/thumbnails
cp media/videos/lbstash-story-1080p60.mp4 $D/videos/
cp media/thumbnails/poster.jpg $D/thumbnails/lbstash-story-poster.jpg
find $D -type f | sort | while read f; do printf "%8s  %s\n" "$(du -h "$f" | cut -f1)" "$f"; done
