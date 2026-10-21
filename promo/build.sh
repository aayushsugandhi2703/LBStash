#!/bin/zsh
# Rebuilds the film and every file in media/ from source. No downloads, no dependencies: Swift and macOS only.
# About a minute. Scratch files go to .work/ (safe to delete).
set -euo pipefail
cd "$(dirname "$0")"
W=.work; mkdir -p $W

swiftc -Ounchecked src/main.swift src/engine/*.swift src/film1/*.swift -o $W/build 2> $W/compile.log || { grep "error:" $W/compile.log; exit 1; }
$W/build --out=$W audio | tail -1
afconvert -f m4af -d aac -b 256000 $W/soundtrack.wav $W/soundtrack.m4a
$W/build --out=$W render | tail -1
$W/build --out=$W mux
$W/build --out=$W thumbs

rm -rf media; mkdir -p media/videos media/audio media/thumbnails
cp $W/master.mp4 media/videos/lbstash-story-1080p60.mp4   # with music: the landing page, ads, YouTube
cp $W/soundtrack.m4a $W/soundtrack.wav media/audio/
mv media/audio/soundtrack.m4a media/audio/lbstash-story-soundtrack.m4a; mv media/audio/soundtrack.wav media/audio/lbstash-story-soundtrack.wav
sips -s format jpeg -s formatOptions 88 $W/thumbs/poster.png --out media/thumbnails/poster.jpg > /dev/null
sips -z 675 1200 $W/thumbs/social.png --out $W/thumbs/social-tmp.png > /dev/null
sips -c 630 1200 $W/thumbs/social-tmp.png --out media/thumbnails/social-1200x630.png > /dev/null
for f in $W/thumbs/thumbnail-*.png; do sips -s format jpeg -s formatOptions 90 $f --out media/thumbnails/$(basename ${f%.png}).jpg > /dev/null; done
find media -type f | sort | while read f; do printf "%8s  %s\n" "$(du -h "$f" | cut -f1)" "$f"; done
