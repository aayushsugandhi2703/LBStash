import Foundation
import CoreGraphics
import AppKit

/// Virtual camera. `zoom` is a dolly (items at different depths scale at different rates, which gives parallax).
struct Cam {
    var x = 0.0, y = 0.0, zoom = 1.0, roll = 0.0
}

let FOCAL = 1500.0

/// Each scene lives on its own "stage" in one big world. Transitions are camera moves between stages.
let stageCenters: [(Double, Double)] = [
    (0, 0), (4200, 0), (8400, 0), (8400, 4200), (12600, 4200), (16800, 4200), (16800, 0), (21000, 0),
]
let stageHalf = 2600.0
let stageColors: [CGColor] = [P.nBg, P.white, P.accent, P.wash, P.nBg, P.white, P.graphite, P.accent]

struct Key {
    var t: Double
    var x = 0.0, y = 0.0, zoom = 1.0, roll = 0.0
    var ease: (Double) -> Double = easeInOutCubic
    /// Extra move on the segment that ends at this key (whips): zoom-out kick (log-zoom) and roll swing (degrees), peaking mid-segment.
    var bumpZoom = 0.0, bumpRoll = 0.0
}

/// Stage-relative key: positions are given relative to a stage centre so the path reads naturally.
func key(_ t: Double, stage: Int, _ x: Double, _ y: Double, zoom: Double = 1, roll: Double = 0, ease: @escaping (Double) -> Double = easeInOutCubic,
         bz: Double = 0, br: Double = 0) -> Key {
    Key(t: t, x: stageCenters[stage].0 + x, y: stageCenters[stage].1 + y, zoom: zoom, roll: roll * .pi / 180, ease: ease, bumpZoom: bz, bumpRoll: br * .pi / 180)
}

func sampleKeys(_ keys: [Key], _ t: Double) -> Cam {
    guard var a = keys.first else { return Cam() }
    if t <= a.t { return Cam(x: a.x, y: a.y, zoom: a.zoom, roll: a.roll) }
    var b: Key? = nil
    for k in keys { if k.t <= t { a = k } else { b = k; break } }
    guard let b else { return Cam(x: a.x, y: a.y, zoom: a.zoom, roll: a.roll) }
    let raw = unlerp(a.t, b.t, t)
    let u = b.ease(raw)
    let bump = sin(Double.pi * raw)
    return Cam(x: lerp(a.x, b.x, u), y: lerp(a.y, b.y, u), zoom: exp(lerp(log(a.zoom), log(b.zoom), u) + b.bumpZoom * bump),
               roll: lerp(a.roll, b.roll, u) + b.bumpRoll * bump)
}

/// Everything a scene needs to draw one frame.
struct View {
    let c: CGContext
    let cam: Cam
    let t: Double

    /// Projects a stage-local point to the screen. Returns scale, position.
    func project(_ stage: Int, _ lx: Double, _ ly: Double, z: Double) -> (s: Double, px: Double, py: Double) {
        let s = cam.zoom / (1 + z * cam.zoom / FOCAL)
        let dx = (stageCenters[stage].0 + lx - cam.x) * s
        let dy = (stageCenters[stage].1 + ly - cam.y) * s
        let cr = cos(cam.roll), sr = sin(cam.roll)
        return (s, W / 2 + dx * cr - dy * sr, H / 2 + dx * sr + dy * cr)
    }

    func projectWorld(_ wx: Double, _ wy: Double, z: Double) -> (s: Double, px: Double, py: Double) {
        let s = cam.zoom / (1 + z * cam.zoom / FOCAL)
        let dx = (wx - cam.x) * s, dy = (wy - cam.y) * s
        let cr = cos(cam.roll), sr = sin(cam.roll)
        return (s, W / 2 + dx * cr - dy * sr, H / 2 + dx * sr + dy * cr)
    }

    /// Draws `body` in item space: origin at the item's anchor, 1 unit = 1 px at the focal plane.
    func at(_ stage: Int, _ lx: Double, _ ly: Double, z: Double = 0, rot: Double = 0, scale: Double = 1, alpha: Double = 1,
            cull: Double = 700, stageOverride: Bool = false, _ body: () -> Void) {
        if scale <= 0.0001 || alpha <= 0.001 { return }
        // stageOverride: lx, ly are absolute world coordinates (stage index is ignored)
        let p = stageOverride ? projectWorld(lx, ly, z: z) : project(stage, lx, ly, z: z)
        let rad = cull * p.s * scale
        if p.px < -rad || p.px > W + rad || p.py < -rad || p.py > H + rad { return }
        c.saveGState()
        c.translateBy(x: CGFloat(p.px), y: CGFloat(p.py))
        c.rotate(by: CGFloat(cam.roll + rot))
        c.scaleBy(x: CGFloat(p.s * scale), y: CGFloat(p.s * scale))
        if alpha < 0.999 {
            c.setAlpha(CGFloat(alpha))
            c.beginTransparencyLayer(auxiliaryInfo: nil)
            body()
            c.endTransparencyLayer()
        } else {
            body()
        }
        c.restoreGState()
    }
}

/// A pop-up: springs in with overshoot, rises and fades in over the first few frames.
struct Pop {
    var s: Double, a: Double, dy: Double
}
func pop(_ t: Double, at t0: Double, rise: Double = 36, damping: Double = 11, freq: Double = 15) -> Pop {
    let x = t - t0
    if x <= 0 { return Pop(s: 0, a: 0, dy: rise) }
    return Pop(s: spring(x, damping: damping, freq: freq), a: clamp(x / 0.07), dy: (1 - easeOutCubic(clamp(x / 0.45))) * rise)
}
/// Pop-out: shrinks and fades after `t0`.
func popOut(_ t: Double, at t0: Double, dur: Double = 0.25) -> Double { 1 - easeInCubic(clamp((t - t0) / dur)) }

/// Kinetic type: the line slides up out of a mask. `t0` is when it starts.
func kText(_ c: CGContext, _ s: String, _ x: Double, _ baseline: Double, size: Double, weight: NSFont.Weight = .black, color: CGColor,
           track: Double = -0.035, t: Double, t0: Double, dur: Double = 0.55, align: Align = .left, mono: Bool = false, out: Double? = nil, outDur: Double = 0.3) {
    var e = easeOutExpo(clamp((t - t0) / dur))
    if let out, t > out { e = 1 - easeInCubic(clamp((t - out) / outDur)) * 1.0; if e <= 0 { return } }
    if t < t0 { return }
    let w = textWidth(s, size: size, weight: weight, track: track, mono: mono)
    let left: Double
    switch align { case .left: left = x; case .center: left = x - w / 2; case .right: left = x - w }
    c.saveGState()
    c.clip(to: rect(left - size * 0.3, baseline - size * 1.0, w + size * 0.6, size * 1.35))
    c.translateBy(x: 0, y: CGFloat((1 - e) * size * 1.15))
    text(c, s, x, baseline, size: size, weight: weight, color: color, track: track, align: align, mono: mono)
    c.restoreGState()
}
