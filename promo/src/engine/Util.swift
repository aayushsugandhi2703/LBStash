import Foundation
import CoreGraphics
import CoreText
import AppKit

// MARK: - Timeline constants (96 BPM: one bar is exactly 2.5 s, so 18 bars = 45 s)

let W = 1920.0
let H = 1080.0
let FPS = 60.0
let BPM = 96.0
let BEAT = 60.0 / BPM
let BAR = BEAT * 4
let S16 = BEAT / 4
/// Length of the film being built; main sets it from the chosen film before anything is rendered.
nonisolated(unsafe) var DURATION = 46.5

// MARK: - Math and easing

@inline(__always) func clamp(_ x: Double, _ a: Double = 0, _ b: Double = 1) -> Double { min(max(x, a), b) }
@inline(__always) func lerp(_ a: Double, _ b: Double, _ t: Double) -> Double { a + (b - a) * t }
@inline(__always) func unlerp(_ a: Double, _ b: Double, _ x: Double) -> Double { b == a ? 1 : clamp((x - a) / (b - a)) }
func easeOutCubic(_ t: Double) -> Double { 1 - pow(1 - t, 3) }
func easeInCubic(_ t: Double) -> Double { t * t * t }
func easeInOutCubic(_ t: Double) -> Double { t < 0.5 ? 4 * t * t * t : 1 - pow(-2 * t + 2, 3) / 2 }
func easeInOutQuint(_ t: Double) -> Double { t < 0.5 ? 16 * pow(t, 5) : 1 - pow(-2 * t + 2, 5) / 2 }
func easeInQuart(_ t: Double) -> Double { t * t * t * t }
func easeOutQuart(_ t: Double) -> Double { 1 - pow(1 - t, 4) }
func easeOutExpo(_ t: Double) -> Double { t >= 1 ? 1 : 1 - pow(2, -10 * t) }
func easeLinear(_ t: Double) -> Double { t }
/// Damped spring that starts at 0, overshoots, settles at 1. `x` is seconds since the event.
func spring(_ x: Double, damping: Double = 11, freq: Double = 15) -> Double {
    x <= 0 ? 0 : 1 - exp(-damping * x) * cos(freq * x)
}
/// Deterministic pseudo-random in 0..1 from an integer seed.
func hash01(_ n: Int) -> Double {
    var x = UInt64(bitPattern: Int64(n)) &* 0x9E3779B97F4A7C15
    x ^= x >> 29; x = x &* 0xBF58476D1CE4E5B9; x ^= x >> 32
    return Double(x & 0xFFFFFF) / Double(0x1000000)
}

// MARK: - Palette (values from frontend/src/app/globals.css and _landing/page.module.css)

func C(_ hex: UInt32, _ a: Double = 1) -> CGColor {
    CGColor(srgbRed: Double((hex >> 16) & 255) / 255, green: Double((hex >> 8) & 255) / 255, blue: Double(hex & 255) / 255, alpha: a)
}
enum P {
    static let ink = C(0x0E0E10), text2 = C(0x3B3B42), muted = C(0x6B6B73), rule = C(0xE6E6EA), track = C(0xEDEDF1)
    static let wash = C(0xF3F3F6), white = C(0xFFFFFF), accent = C(0x00875A), accentLight = C(0x00A06B), accentDark = C(0x005C3D)
    static let accentPale = C(0xC9EEDD), ribbon = C(0xD8F3E7), warn = C(0xE9A800), warnText = C(0x8A6200), danger = C(0xC93030)
    static let nBg = C(0x0E0E10), nPanel = C(0x17171B), nLine = C(0x3C3C45), nDim = C(0x8E8E98), nFg = C(0xECECF0)
    static let nGreen = C(0x2DC890), nRed = C(0xF2706A), graphite = C(0x2B3236)
}
func withAlpha(_ c: CGColor, _ a: Double) -> CGColor { c.copy(alpha: CGFloat(a)) ?? c }

// MARK: - Text

enum Align { case left, center, right }

private let fontLock = NSLock()
private nonisolated(unsafe) var fontCache: [String: CTFont] = [:]
/// Brand fonts are Geist and Geist Mono. If they are installed, run with LB_FONT_SANS="Geist" LB_FONT_MONO="Geist Mono";
/// otherwise the macOS system fonts stand in.
private let sansFamily = ProcessInfo.processInfo.environment["LB_FONT_SANS"]
private let monoFamily = ProcessInfo.processInfo.environment["LB_FONT_MONO"]

func font(_ size: Double, _ weight: NSFont.Weight, mono: Bool) -> CTFont {
    let key = "\(size)|\(weight.rawValue)|\(mono)"
    fontLock.lock(); defer { fontLock.unlock() }
    if let f = fontCache[key] { return f }
    var nf: NSFont? = nil
    if let family = mono ? monoFamily : sansFamily {
        let d = NSFontDescriptor(fontAttributes: [.family: family, .traits: [NSFontDescriptor.TraitKey.weight: weight.rawValue]])
        nf = NSFont(descriptor: d, size: CGFloat(size))
    }
    let resolved = nf ?? (mono ? NSFont.monospacedSystemFont(ofSize: CGFloat(size), weight: weight) : NSFont.systemFont(ofSize: CGFloat(size), weight: weight))
    let f = resolved as CTFont
    fontCache[key] = f
    return f
}

private func makeLine(_ s: String, size: Double, weight: NSFont.Weight, color: CGColor, track: Double, mono: Bool) -> CTLine {
    let attrs: [NSAttributedString.Key: Any] = [
        NSAttributedString.Key(kCTFontAttributeName as String): font(size, weight, mono: mono),
        NSAttributedString.Key(kCTForegroundColorAttributeName as String): color,
        NSAttributedString.Key(kCTKernAttributeName as String): track * size,
    ]
    return CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: attrs))
}

func textWidth(_ s: String, size: Double, weight: NSFont.Weight = .semibold, track: Double = 0, mono: Bool = false) -> Double {
    let l = makeLine(s, size: size, weight: weight, color: P.ink, track: track, mono: mono)
    return CTLineGetTypographicBounds(l, nil, nil, nil) - (track == 0 ? 0 : track * size)
}

/// Draws one line of text with its baseline at `y`. The context is y-down (flipped), so text is flipped back here.
@discardableResult
func text(_ c: CGContext, _ s: String, _ x: Double, _ y: Double, size: Double, weight: NSFont.Weight = .semibold,
          color: CGColor = P.ink, track: Double = 0, align: Align = .left, mono: Bool = false) -> Double {
    let line = makeLine(s, size: size, weight: weight, color: color, track: track, mono: mono)
    let w = CTLineGetTypographicBounds(line, nil, nil, nil) - (track == 0 ? 0 : track * size)
    let ox: Double
    switch align { case .left: ox = x; case .center: ox = x - w / 2; case .right: ox = x - w }
    c.saveGState()
    c.textMatrix = CGAffineTransform(scaleX: 1, y: -1)
    c.textPosition = CGPoint(x: ox, y: y)
    CTLineDraw(line, c)
    c.restoreGState()
    return w
}

// MARK: - Shapes

func rect(_ x: Double, _ y: Double, _ w: Double, _ h: Double) -> CGRect { CGRect(x: x, y: y, width: w, height: h) }
func fill(_ c: CGContext, _ r: CGRect, _ color: CGColor) { c.setFillColor(color); c.fill(r) }
func stroke(_ c: CGContext, _ r: CGRect, _ color: CGColor, _ lw: Double = 2) {
    c.setStrokeColor(color); c.setLineWidth(CGFloat(lw)); c.stroke(r.insetBy(dx: CGFloat(lw / 2), dy: CGFloat(lw / 2)))
}
func line(_ c: CGContext, _ x1: Double, _ y1: Double, _ x2: Double, _ y2: Double, _ color: CGColor, _ lw: Double = 2, dash: [CGFloat] = []) {
    c.saveGState()
    c.setStrokeColor(color); c.setLineWidth(CGFloat(lw)); c.setLineDash(phase: 0, lengths: dash)
    c.move(to: CGPoint(x: x1, y: y1)); c.addLine(to: CGPoint(x: x2, y: y2)); c.strokePath()
    c.restoreGState()
}
func circle(_ c: CGContext, _ cx: Double, _ cy: Double, _ r: Double, fill f: CGColor? = nil, stroke s: CGColor? = nil, lw: Double = 2) {
    let r = CGRect(x: cx - r, y: cy - r, width: r * 2, height: r * 2)
    if let f { c.setFillColor(f); c.fillEllipse(in: r) }
    if let s { c.setStrokeColor(s); c.setLineWidth(CGFloat(lw)); c.strokeEllipse(in: r) }
}
/// Diagonal stripes inside `r` (the "forecast" fill used across the product).
func hatch(_ c: CGContext, _ r: CGRect, gap: Double = 8, lw: Double = 2, color: CGColor) {
    c.saveGState()
    c.clip(to: r)
    c.setStrokeColor(color); c.setLineWidth(CGFloat(lw))
    var x = -Double(r.height)
    while x < Double(r.width) {
        c.move(to: CGPoint(x: Double(r.minX) + x, y: Double(r.maxY)))
        c.addLine(to: CGPoint(x: Double(r.minX) + x + Double(r.height), y: Double(r.minY)))
        x += gap
    }
    c.strokePath()
    c.restoreGState()
}
/// White box, ink border, hard offset shadow. The "pop-up card" used throughout the film.
func card(_ c: CGContext, _ r: CGRect, fill f: CGColor = P.white, border: CGColor = P.ink, lw: Double = 2,
          shadow: CGColor? = P.ink, off: Double = 10) {
    if let shadow { fill(c, r.offsetBy(dx: CGFloat(off), dy: CGFloat(off)), shadow) }
    fill(c, r, f)
    if lw > 0 { stroke(c, r, border, lw) }
}
func chip(_ c: CGContext, _ s: String, cx: Double, cy: Double, size: Double = 26, fg: CGColor = P.accent, bg: CGColor = P.ribbon, border: CGColor? = nil) {
    let w = textWidth(s, size: size, weight: .semibold, mono: true) + size * 1.1
    let h = size * 1.75
    let r = rect(cx - w / 2, cy - h / 2, w, h)
    fill(c, r, bg)
    if let border { stroke(c, r, border, 1.5) }
    text(c, s, cx, cy + size * 0.34, size: size, weight: .semibold, color: fg, align: .center, mono: true)
}
/// The logo mark: a lowercase b made of a stem and a coin, white on a green square. `s` is the tile size.
func logoMark(_ c: CGContext, cx: Double, cy: Double, s: Double, tile: CGColor = P.accent, ink: CGColor = P.white) {
    let u = s / 32
    let x0 = cx - s / 2, y0 = cy - s / 2
    fill(c, rect(x0, y0, s, s), tile)
    fill(c, rect(x0 + 8 * u, y0 + 5 * u, 5.5 * u, 22 * u), ink)
    circle(c, x0 + 20.5 * u, y0 + 20.5 * u, 6.5 * u, fill: ink)
}
func wordmark(_ c: CGContext, x: Double, baseline: Double, size: Double, lb: CGColor, stash: CGColor, align: Align = .left) {
    let w1 = textWidth("LB", size: size, weight: .semibold, track: -0.03)
    let w2 = textWidth("Stash", size: size, weight: .semibold, track: -0.03)
    let total = w1 + w2 - size * 0.03
    let sx: Double
    switch align { case .left: sx = x; case .center: sx = x - total / 2; case .right: sx = x - total }
    text(c, "LB", sx, baseline, size: size, weight: .semibold, color: lb, track: -0.03)
    text(c, "Stash", sx + w1, baseline, size: size, weight: .semibold, color: stash, track: -0.03)
}

func inr(_ n: Int) -> String {
    let f = NumberFormatter(); f.numberStyle = .decimal; f.locale = Locale(identifier: "en_IN"); f.groupingSize = 3; f.secondaryGroupingSize = 2
    return f.string(from: NSNumber(value: n)) ?? "\(n)"
}
