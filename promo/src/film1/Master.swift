import Foundation

/// Mixes every bus, adds reverb, shapes the intro, then compresses and limits. Returns stereo float at 48 kHz.
func renderFilm1Audio() -> (l: [Float], r: [Float]) {
    let song = Song()
    song.compose()
    song.design()

    if ProcessInfo.processInfo.environment["STEMS"] != nil {
        func rms(_ b: Bus, _ t0: Double, _ t1: Double) -> String {
            var s = 0.0; let a = Int(t0 * SR), z = Int(t1 * SR)
            for i in a..<z { s += Double(b.l[i] * b.l[i] + b.r[i] * b.r[i]) * 0.5 }
            return String(format: "%6.1f", 20 * log10(max(1e-9, sqrt(s / Double(z - a)))))
        }
        for (name, t0, t1) in [("groove 5-15s", 5.0, 15.0), ("peak 25-30s", 25.0, 30.0), ("privacy 30-35s", 30.0, 35.0)] {
            print("\(name): drums\(rms(song.drums, t0, t1)) bass\(rms(song.bass, t0, t1)) keys\(rms(song.keys, t0, t1)) sax\(rms(song.sax, t0, t1)) sfx\(rms(song.sfx, t0, t1)) roll\(rms(song.roll, t0, t1))")
        }
        try? writeWav(song.sax.l, song.sax.r, to: "out/stem-sax.wav")
        try? writeWav(song.drums.l, song.drums.r, to: "out/stem-drums.wav")
        var rs = 0.0; for i in 0..<AUDIO_N { rs += Double(song.revSend[i] * song.revSend[i]) }
        print(String(format: "reverb send rms %.1f dB", 20 * log10(max(1e-9, sqrt(rs / Double(AUDIO_N))))))
    }
    var l = [Float](repeating: 0, count: AUDIO_N), r = l
    // music: drums, bass, keys, sax (+ the snare rolls). The intro is heard "through a wall" and opens up on the drop at 5.0 s.
    var lpL = 0.0, lpR = 0.0
    for i in 0..<AUDIO_N {
        let t = Double(i) / SR
        let ml = Double(song.drums.l[i] + song.bass.l[i] + song.keys.l[i] + song.sax.l[i] + song.roll.l[i])
        let mr = Double(song.drums.r[i] + song.bass.r[i] + song.keys.r[i] + song.sax.r[i] + song.roll.r[i])
        if t < 5.0 {
            let fc = 380 * pow(40, min(1, t / 4.85))
            let a = 1 - exp(-2 * Double.pi * fc / SR)
            lpL += a * (ml - lpL); lpR += a * (mr - lpR)
            l[i] = Float(lpL); r[i] = Float(lpR)
        } else {
            l[i] = Float(ml); r[i] = Float(mr)
        }
    }
    // vinyl crackle: obvious in the intro, a whisper afterwards
    let crackle = vinyl(dur: DURATION)
    for i in 0..<AUDIO_N {
        let t = Double(i) / SR
        let g: Float = t < 5.0 ? 0.9 : (t < 5.3 ? Float(0.9 - (t - 5.0) / 0.3 * 0.78) : 0.12)
        l[i] += crackle[i] * g; r[i] += crackle[(i + 977) % AUDIO_N] * g
    }
    // reverb return
    let (rl, rr) = Reverb.process(song.revSend, room: 0.86, damp: 0.32, width: 1.0)
    for i in 0..<AUDIO_N { l[i] += rl[i] * 0.7; r[i] += rr[i] * 0.7 }
    // sound design on top, dry
    for i in 0..<AUDIO_N { l[i] += song.sfx.l[i]; r[i] += song.sfx.r[i] }

    // bus compressor (stereo-linked), then level to a streaming-friendly loudness, then soft limit
    var env = 0.0
    let thr = 0.30, ratio = 2.6
    let atk = exp(-1 / (0.006 * SR)), rel = exp(-1 / (0.14 * SR))
    for i in 0..<AUDIO_N {
        let pk = Double(max(abs(l[i]), abs(r[i])))
        env = pk > env ? atk * env + (1 - atk) * pk : rel * env + (1 - rel) * pk
        let g = env > thr ? pow(env / thr, 1 / ratio - 1) : 1
        l[i] *= Float(g); r[i] *= Float(g)
    }
    var sumSq = 0.0
    var idx = 0
    for i in 0..<AUDIO_N where Double(i) / SR > 5.0 && Double(i) / SR < 40.0 { sumSq += Double(l[i] * l[i] + r[i] * r[i]) * 0.5; idx += 1 }
    let rms = sqrt(sumSq / Double(max(idx, 1)))
    let targetRMS = pow(10, -15.5 / 20)
    let gain = Float(targetRMS / rms)
    func soft(_ x: Float) -> Float {
        let a = abs(x), k: Float = 0.72
        if a < k { return x }
        let y = k + (1 - k) * Float(tanh(Double((a - k) / (1 - k))))
        return x < 0 ? -y : y
    }
    // a hair of vacuum right before the big hits, so each one lands harder
    let dips: [(Double, Double)] = [(4.925, 5.0), (19.88, 20.0), (24.925, 25.0), (29.925, 30.0), (39.925, 40.0)]
    // DC blocker
    var dcLx = 0.0, dcLy = 0.0, dcRx = 0.0, dcRy = 0.0
    for i in 0..<AUDIO_N {
        let xl = Double(l[i]), xr = Double(r[i])
        dcLy = xl - dcLx + 0.9995 * dcLy; dcLx = xl
        dcRy = xr - dcRx + 0.9995 * dcRy; dcRx = xr
        l[i] = Float(dcLy); r[i] = Float(dcRy)
    }
    let fadeStart = DURATION - 1.4
    for i in 0..<AUDIO_N {
        let t = Double(i) / SR
        var f: Float = 1
        for (a, b) in dips where t >= a - 0.004 && t < b + 0.0005 {
            let into = min(1, max(0, (t - (a - 0.004)) / 0.004))
            f *= Float(1 - 0.9 * into)
        }
        if t > fadeStart { let u = Float((t - fadeStart) / 1.4); f = (1 - u) * (1 - u) }
        if t < 0.004 { f *= Float(t / 0.004) }
        l[i] = soft(l[i] * gain) * 0.89 * f
        r[i] = soft(r[i] * gain) * 0.89 * f
    }
    return (l, r)
}

func writeWav(_ l: [Float], _ r: [Float], to path: String) throws {
    var data = Data()
    let n = l.count
    func u32(_ v: UInt32) { var x = v.littleEndian; withUnsafeBytes(of: &x) { data.append(contentsOf: $0) } }
    func u16(_ v: UInt16) { var x = v.littleEndian; withUnsafeBytes(of: &x) { data.append(contentsOf: $0) } }
    data.append("RIFF".data(using: .ascii)!); u32(UInt32(36 + n * 4)); data.append("WAVE".data(using: .ascii)!)
    data.append("fmt ".data(using: .ascii)!); u32(16); u16(1); u16(2); u32(UInt32(SR)); u32(UInt32(SR) * 4); u16(4); u16(16)
    data.append("data".data(using: .ascii)!); u32(UInt32(n * 4))
    var pcm = [Int16](repeating: 0, count: n * 2)
    for i in 0..<n {
        pcm[2 * i] = Int16(max(-32767, min(32767, l[i] * 32767)))
        pcm[2 * i + 1] = Int16(max(-32767, min(32767, r[i] * 32767)))
    }
    pcm.withUnsafeBytes { data.append(contentsOf: $0) }
    try data.write(to: URL(fileURLWithPath: path))
}

func audioReport(_ l: [Float], _ r: [Float]) {
    var peak: Float = 0
    for i in 0..<l.count { peak = max(peak, abs(l[i]), abs(r[i])) }
    func db(_ x: Double) -> String { String(format: "%6.1f", 20 * log10(max(x, 1e-9))) }
    print("peak \(db(Double(peak))) dBFS")
    var line = "per-bar RMS (dBFS):"
    for bar in 0..<19 {
        let a = Int(Double(bar) * BAR * SR), b = min(l.count, Int(Double(bar + 1) * BAR * SR))
        if a >= b { break }
        var s = 0.0
        for i in a..<b { s += Double(l[i] * l[i] + r[i] * r[i]) * 0.5 }
        line += "\n  bar \(String(format: "%2d", bar)) [\(String(format: "%5.1f", Double(bar) * BAR))s] \(db(sqrt(s / Double(b - a))))"
    }
    print(line)
}
