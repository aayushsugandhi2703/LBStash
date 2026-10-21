# LBStash promo film

A 46.5 s film of the product ("It's day 21. Where's your month going?"), made from code: Swift and the frameworks that ship with macOS, nothing to download. The music is original (hip-hop, 96 BPM, sax-style lead, synthesized, no samples), so there is nothing to license.

```
media/        finished files (git-ignored; made by ./build.sh)
  videos/     lbstash-story-1080p60.mp4          1080p, 60 fps, with music: the landing page, ads, YouTube
  audio/      lbstash-story-soundtrack.m4a / .wav
  thumbnails/ poster.jpg, social-1200x630.png, thumbnail-1.jpg, thumbnail-2.jpg
src/
  engine/     drawing helpers, synth, video encoder (motion blur, H.264)
  film1/      the scenes, camera path and music
build.sh      rebuilds everything in about a minute
sync-web.sh   copies the film and poster to ../frontend/public/promo/
```

The landing page plays the film in `frontend/public/promo/` (a muted loop, with a "Watch with sound" button) through `frontend/src/app/_landing/film.tsx`. After a rebuild, run `./sync-web.sh`.

The brand font is Geist, which is not installed here, so the macOS system font stands in. With Geist installed: `LB_FONT_SANS="Geist" LB_FONT_MONO="Geist Mono" ./build.sh`.

| To change | Edit |
|---|---|
| Timing of every pop (picture and sound share it) | `TL` in `film1/ScenesA.swift` |
| Camera moves, whips, cuts | `cameraKeys` in `film1/Timeline.swift` |
| Copy, layout, cards | `film1/ScenesA.swift`, `film1/ScenesB.swift` |
| Music and sound effects | `film1/Music.swift`, `engine/Synth.swift`, `film1/Master.swift` |
| Video quality | `renderVideo` in `engine/Video.swift` |

`.work/build still 28.6 42.9` renders single frames to `.work/story-46s/stills/`.
