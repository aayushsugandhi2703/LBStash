import Foundation
import CoreGraphics

/// A film is a pure function of time (picture), plus a soundtrack. The pipeline renders, blurs, encodes and muxes any film the same way.
protocol Film {
    /// Folder-friendly name, e.g. "story-45s".
    var slug: String { get }
    var duration: Double { get }
    /// Hard cuts in the picture: motion blur must never straddle one.
    var cuts: [Double] { get }
    /// Draws one instant into a 1920x1080 y-down context.
    func renderInstant(_ c: CGContext, t: Double)
    /// How many sub-frames to average for frame time `t`, and how much of the frame interval the shutter stays open.
    func blurPlan(_ t: Double) -> (n: Int, shutter: Double)
    /// Optional pass over the finished (motion-blurred) BGRA frame.
    func postFrame(_ px: UnsafeMutablePointer<UInt8>, t: Double)
    func renderAudio() -> (l: [Float], r: [Float])
    /// Times of the frames to save as posters and thumbnails.
    var stillTimes: (poster: Double, thumbnails: [Double], social: Double) { get }
}

extension Film {
    func postFrame(_ px: UnsafeMutablePointer<UInt8>, t: Double) {}
}
