import Foundation
import CoreGraphics

/// Film 1: the 46.5 s story ("It's day 21").
struct Film1: Film {
    let slug = "story-46s"
    let duration = 46.5
    let cuts: [Double] = [20.0]
    var stillTimes: (poster: Double, thumbnails: [Double], social: Double) { (3.9, [28.6, 42.9], 42.2) }

    func renderInstant(_ c: CGContext, t: Double) { film1Instant(c, t: t) }
    func renderAudio() -> (l: [Float], r: [Float]) { renderFilm1Audio() }

    /// Each output frame averages several instants across the shutter, more when the camera moves fast.
    func blurPlan(_ t: Double) -> (n: Int, shutter: Double) {
        if cuts.contains(where: { abs($0 - t) < 0.02 }) { return (3, 0.5) }
        let dt = 0.004
        let a = cameraAt(t - dt), b = cameraAt(t + dt)
        let z = (a.zoom + b.zoom) / 2
        let sp = (hypot(b.x - a.x, b.y - a.y) * z + abs(b.roll - a.roll) * 700 + abs(log(b.zoom / a.zoom)) * 1000) / (2 * dt)
        let shutter = min(0.92, max(0.5, 0.5 + sp / 8000))
        let smear = sp * shutter / FPS
        return (max(3, min(48, Int(ceil(smear / 3.0)))), shutter)
    }
}
