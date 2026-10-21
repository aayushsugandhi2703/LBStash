import Foundation
import CoreGraphics

// Usage: build [--out=DIR] <command>
//   still <t...>   PNG of single instants (no motion blur)
//   audio          the soundtrack as WAV
//   render         the video (1080p, 60 fps)
//   mux            add soundtrack.m4a to it
//   thumbs         the poster, thumbnails and social image as PNGs

var args = Array(CommandLine.arguments.dropFirst())
func option(_ name: String) -> String? {
    guard let i = args.firstIndex(where: { $0.hasPrefix("--\(name)=") }) else { return nil }
    let v = String(args[i].dropFirst(name.count + 3)); args.remove(at: i); return v
}
let film: Film = Film1()
DURATION = film.duration
let outDir = option("out") ?? ".work/\(film.slug)"
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

func still(_ t: Double) -> CGContext {
    let c = makeContext(1920, 1080)
    film.renderInstant(c, t: t)
    film.postFrame(c.data!.assumingMemoryBound(to: UInt8.self), t: t)
    return c
}

switch args.first ?? "" {
case "still":
    try? FileManager.default.createDirectory(atPath: "\(outDir)/stills", withIntermediateDirectories: true)
    for t in args.dropFirst().compactMap({ Double($0) }) {
        let path = "\(outDir)/stills/t\(String(format: "%06.2f", t)).png"
        try! pngData(still(t).makeImage()!).write(to: URL(fileURLWithPath: path))
        print(path)
    }
case "thumbs":
    let st = film.stillTimes
    try? FileManager.default.createDirectory(atPath: "\(outDir)/thumbs", withIntermediateDirectories: true)
    var jobs: [(String, Double)] = [("poster", st.poster), ("social", st.social)]
    for (i, t) in st.thumbnails.enumerated() { jobs.append(("thumbnail-\(i + 1)", t)) }
    for (name, t) in jobs { try! pngData(still(t).makeImage()!).write(to: URL(fileURLWithPath: "\(outDir)/thumbs/\(name).png")) }
case "audio":
    let (l, r) = film.renderAudio()
    try! writeWav(l, r, to: "\(outDir)/soundtrack.wav")
    audioReport(l, r)
case "render":
    try! renderVideo(film, outDir: outDir, frames: 0..<Int(film.duration * FPS))
case "mux":
    muxAudio(video: "\(outDir)/master-silent.mp4", audio: "\(outDir)/soundtrack.m4a", output: "\(outDir)/master.mp4")
    print("muxed")
default:
    print("usage: build [--out=DIR] still|thumbs|audio|render|mux")
}
