import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!

func makeContext(_ w: Int, _ h: Int) -> CGContext {
    let c = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0, space: colorSpace,
                      bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
    c.interpolationQuality = .high
    c.setShouldAntialias(true); c.setAllowsAntialiasing(true)
    c.setShouldSmoothFonts(false)
    return c
}

/// Draws one instant of the film into a 1920x1080 y-down context.
func film1Instant(_ c: CGContext, t: Double) {
    c.saveGState()
    c.translateBy(x: 0, y: CGFloat(CGFloat(c.height) ))
    c.scaleBy(x: CGFloat(c.width) / CGFloat(W), y: -CGFloat(c.height) / CGFloat(H))
    let cam = cameraAt(t)
    let v = View(c: c, cam: cam, t: t)
    fill(c, rect(0, 0, W, H), P.nBg)
    drawBackdrop(v)
    drawWhipStreaks(v)
    scene0(v); scene1(v); scene2(v); scene3(v); scene4(v); scene5(v); scene6(v); scene7(v)
    drawPost(c, t: t, cam: cam)
    c.restoreGState()
}

// MARK: - Post: logo bug, vignette, beat flashes

let flashes: [(Double, Double, UInt32)] = [(0.0, 0.3, 0xFFFFFF), (2.5, 0.25, 0x2DC890), (5.0, 0.3, 0xFFFFFF), (10.0, 0.25, 0xFFFFFF), (20.0, 0.55, 0xFFFFFF), (24.4, 0.4, 0xF2706A), (30.0, 0.35, 0xFFFFFF), (33.75, 0.3, 0xFFFFFF), (40.0, 0.7, 0xFFFFFF)]

func drawPost(_ c: CGContext, t: Double, cam: Cam) {
    // logo bug, top right: on the light and green scenes only (the dark scenes carry their own big type)
    if t > 5.2 && t < 39.6 {
        var stage = 0
        for i in 0..<stageCenters.count where abs(cam.x - stageCenters[i].0) <= stageHalf && abs(cam.y - stageCenters[i].1) <= stageHalf { stage = i }
        if [1, 2, 3, 5].contains(stage) {
            let a = min(clamp((t - 5.2) / 0.4), clamp((39.6 - t) / 0.3), clamp((1.3 - cam.zoom) / 0.15)) // steps aside during close-ups
            c.saveGState(); c.setAlpha(CGFloat(a))
            if stage == 2 {
                logoMark(c, cx: 1722, cy: 62, s: 40, tile: .clear, ink: P.white)
                wordmark(c, x: 1752, baseline: 72, size: 31, lb: P.white, stash: P.white)
            } else {
                logoMark(c, cx: 1722, cy: 62, s: 40)
                wordmark(c, x: 1752, baseline: 72, size: 31, lb: P.ink, stash: P.accent)
            }
            c.restoreGState()
        }
    }
    // vignette
    let g = CGGradient(colorsSpace: colorSpace, colors: [C(0x000000, 0), C(0x000000, 0.22)] as CFArray, locations: [0.55, 1])!
    c.drawRadialGradient(g, startCenter: CGPoint(x: W / 2, y: H / 2), startRadius: 0, endCenter: CGPoint(x: W / 2, y: H / 2), endRadius: CGFloat(hypot(W, H) / 2), options: .drawsAfterEndLocation)
    // beat flashes
    for (ft, strength, col) in flashes where t >= ft && t < ft + 0.3 {
        let a = strength * pow(1 - (t - ft) / 0.3, 2.2)
        fill(c, rect(0, 0, W, H), C(col, a))
    }
}

func pngData(_ img: CGImage) -> Data {
    let d = NSMutableData()
    let dest = CGImageDestinationCreateWithData(d, UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(dest, img, nil)
    CGImageDestinationFinalize(dest)
    return d as Data
}
