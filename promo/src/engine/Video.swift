import Foundation
import AVFoundation
import CoreVideo
import CoreGraphics

// MARK: - Motion blur: each output frame averages several instants across the shutter, more when the camera moves fast

/// Renders one finished frame (1920x1080 BGRA, premultiplied) and returns its pixels. Caller frees the pointer.
func renderFrame(_ film: Film, _ index: Int) -> UnsafeMutablePointer<UInt8> {
    let t = Double(index) / FPS
    let plan = film.blurPlan(t)
    let ctx = makeContext(1920, 1080)
    let total = ctx.bytesPerRow * ctx.height
    let out = UnsafeMutablePointer<UInt8>.allocate(capacity: total)
    if plan.n == 1 {
        film.renderInstant(ctx, t: t)
        memcpy(out, ctx.data!, total)
        film.postFrame(out, t: t)
        return out
    }
    let acc = UnsafeMutablePointer<UInt16>.allocate(capacity: total)
    acc.initialize(repeating: 0, count: total)
    let src = ctx.data!.assumingMemoryBound(to: UInt8.self)
    for i in 0..<plan.n {
        var ti = t + ((Double(i) + 0.5) / Double(plan.n) - 0.5) * plan.shutter / FPS
        for cut in film.cuts where abs(cut - t) < 0.02 { ti = t >= cut ? max(ti, cut) : min(ti, cut - 0.0001) }
        film.renderInstant(ctx, t: ti)
        for k in 0..<total { acc[k] &+= UInt16(src[k]) }
    }
    let n = UInt16(plan.n), half = n / 2
    for k in 0..<total { out[k] = UInt8((acc[k] &+ half) / n) }
    acc.deallocate()
    film.postFrame(out, t: t)
    return out
}

// MARK: - Encoder

final class Encoder {
    let writer: AVAssetWriter
    let input: AVAssetWriterInput
    let adaptor: AVAssetWriterInputPixelBufferAdaptor
    let width: Int, height: Int, fps: Int32
    let every: Int
    var written = 0

    init(path: String, width: Int, height: Int, fps: Int32, bitrate: Int, every: Int) throws {
        self.width = width; self.height = height; self.fps = fps; self.every = every
        try? FileManager.default.removeItem(atPath: path)
        writer = try AVAssetWriter(outputURL: URL(fileURLWithPath: path), fileType: .mp4)
        let settings: [String: Any] = [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width, AVVideoHeightKey: height,
            AVVideoColorPropertiesKey: [
                AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
                AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
            ],
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: bitrate,
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
                AVVideoMaxKeyFrameIntervalKey: Int(fps) * 2,
                AVVideoExpectedSourceFrameRateKey: Int(fps),
                AVVideoH264EntropyModeKey: AVVideoH264EntropyModeCABAC,
            ],
        ]
        input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = false
        adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: width, kCVPixelBufferHeightKey as String: height,
            kCVPixelBufferCGBitmapContextCompatibilityKey as String: true,
        ])
        writer.add(input)
        writer.shouldOptimizeForNetworkUse = true
        guard writer.startWriting() else { throw writer.error ?? NSError(domain: "encoder", code: 1) }
        writer.startSession(atSourceTime: .zero)
    }

    /// `frame` is a 1920x1080 BGRA frame at 60 fps; this encoder keeps every `every`-th one. `tailFade` blends to ink for loop-friendly ends.
    func append(frame: UnsafeMutablePointer<UInt8>, index: Int, tailFade: Double = 0) {
        if index % every != 0 { return }
        while !input.isReadyForMoreMediaData { usleep(1000) }
        var pb: CVPixelBuffer?
        CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb)
        guard let pb else { return }
        CVPixelBufferLockBaseAddress(pb, [])
        let base = CVPixelBufferGetBaseAddress(pb)!
        let bpr = CVPixelBufferGetBytesPerRow(pb)
        if width == 1920 {
            for y in 0..<1080 { memcpy(base + y * bpr, frame + y * 1920 * 4, 1920 * 4) }
        } else {
            let src = CGContext(data: frame, width: 1920, height: 1080, bitsPerComponent: 8, bytesPerRow: 1920 * 4, space: colorSpace,
                                bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
            let dst = CGContext(data: base, width: width, height: height, bitsPerComponent: 8, bytesPerRow: bpr, space: colorSpace,
                                bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue)!
            dst.interpolationQuality = .high
            dst.draw(src.makeImage()!, in: CGRect(x: 0, y: 0, width: width, height: height))
            if tailFade > 0 { dst.setFillColor(C(0x0E0E10, tailFade)); dst.fill(CGRect(x: 0, y: 0, width: width, height: height)) }
        }
        CVPixelBufferUnlockBaseAddress(pb, [])
        let pts = CMTime(value: CMTimeValue(written), timescale: fps)
        adaptor.append(pb, withPresentationTime: pts)
        written += 1
    }

    func finish() {
        input.markAsFinished()
        let sem = DispatchSemaphore(value: 0)
        writer.finishWriting { sem.signal() }
        sem.wait()
        if writer.status != .completed { print("encoder error: \(String(describing: writer.error))") }
    }
}

func renderVideo(_ film: Film, outDir: String, frames: Range<Int>) throws {
    let master = try Encoder(path: "\(outDir)/master-silent.mp4", width: 1920, height: 1080, fps: 60, bitrate: 14_000_000, every: 1)
    let batch = 24
    let start = Date()
    var i = frames.lowerBound
    while i < frames.upperBound {
        let n = min(batch, frames.upperBound - i)
        var results = [UnsafeMutablePointer<UInt8>?](repeating: nil, count: n)
        let lock = NSLock()
        let base = i
        DispatchQueue.concurrentPerform(iterations: n) { k in
            let f = renderFrame(film, base + k)
            lock.lock(); results[k] = f; lock.unlock()
        }
        for k in 0..<n {
            let idx = base + k
            let t = Double(idx) / FPS
            let f = results[k]!
            master.append(frame: f, index: idx - frames.lowerBound)
            f.deallocate()
        }
        i += n
        if (i / batch) % 5 == 0 || i >= frames.upperBound {
            let el = Date().timeIntervalSince(start), done = Double(i - frames.lowerBound), total = Double(frames.count)
            print(String(format: "frame %d/%d  %.0fs elapsed  ~%.0fs left", i - frames.lowerBound, frames.count, el, el / done * (total - done)))
            fflush(stdout)
        }
    }
    master.finish()
}

// MARK: - Mux video + soundtrack

func muxAudio(video: String, audio: String, output: String) {
    try? FileManager.default.removeItem(atPath: output)
    let comp = AVMutableComposition()
    let v = AVURLAsset(url: URL(fileURLWithPath: video)), a = AVURLAsset(url: URL(fileURLWithPath: audio))
    let sem = DispatchSemaphore(value: 0)
    Task {
        do {
            let vt = try await v.loadTracks(withMediaType: .video).first!
            let at = try await a.loadTracks(withMediaType: .audio).first!
            let vd = try await v.load(.duration)
            let ct = comp.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)!
            try ct.insertTimeRange(CMTimeRange(start: .zero, duration: vd), of: vt, at: .zero)
            let ca = comp.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid)!
            try ca.insertTimeRange(CMTimeRange(start: .zero, duration: vd), of: at, at: .zero)
            let ex = AVAssetExportSession(asset: comp, presetName: AVAssetExportPresetPassthrough)!
            ex.outputURL = URL(fileURLWithPath: output); ex.outputFileType = .mp4; ex.shouldOptimizeForNetworkUse = true
            await ex.export()
            if ex.status != .completed { print("mux error: \(String(describing: ex.error))") }
        } catch { print("mux failed: \(error)") }
        sem.signal()
    }
    sem.wait()
}
