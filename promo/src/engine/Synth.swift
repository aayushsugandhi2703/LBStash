import Foundation

// MARK: - Basics

let SR = 48000.0
var AUDIO_N: Int { Int(DURATION * SR) }

struct Rng {
    var s: UInt64
    init(_ seed: UInt64) { s = (seed &* 0x9E3779B97F4A7C15) | 1 }
    /// -1 ... 1
    mutating func next() -> Double {
        s ^= s << 13; s ^= s >> 7; s ^= s << 17
        return Double(s >> 11) / Double(UInt64(1) << 53) * 2 - 1
    }
}

func midiHz(_ m: Double) -> Double { 440 * pow(2, (m - 69) / 12) }

/// RBJ biquad.
struct Biquad {
    var b0 = 1.0, b1 = 0.0, b2 = 0.0, a1 = 0.0, a2 = 0.0
    var x1 = 0.0, x2 = 0.0, y1 = 0.0, y2 = 0.0
    enum Kind { case lowpass, highpass, bandpass, peaking(Double) }
    init(_ kind: Kind, fc: Double, q: Double = 0.707) {
        let w = 2 * Double.pi * min(fc, SR * 0.45) / SR, cw = cos(w), sw = sin(w), al = sw / (2 * q)
        var a0 = 1.0
        switch kind {
        case .lowpass: b0 = (1 - cw) / 2; b1 = 1 - cw; b2 = (1 - cw) / 2; a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al
        case .highpass: b0 = (1 + cw) / 2; b1 = -(1 + cw); b2 = (1 + cw) / 2; a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al
        case .bandpass: b0 = al; b1 = 0; b2 = -al; a0 = 1 + al; a1 = -2 * cw; a2 = 1 - al
        case .peaking(let db):
            let A = pow(10, db / 40)
            b0 = 1 + al * A; b1 = -2 * cw; b2 = 1 - al * A; a0 = 1 + al / A; a1 = -2 * cw; a2 = 1 - al / A
        }
        b0 /= a0; b1 /= a0; b2 /= a0; a1 /= a0; a2 /= a0
    }
    @inline(__always) mutating func process(_ x: Double) -> Double {
        let y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = x; y2 = y1; y1 = y
        return y
    }
}

/// Chamberlin state-variable filter, safe to sweep.
struct SVF {
    var low = 0.0, band = 0.0
    mutating func bandpass(_ x: Double, fc: Double, q: Double) -> Double {
        let f = 2 * sin(Double.pi * min(fc, SR * 0.2) / SR)
        low += f * band
        let high = x - low - band / q
        band += f * high
        return band
    }
    mutating func lowpass(_ x: Double, fc: Double, q: Double) -> Double {
        let f = 2 * sin(Double.pi * min(fc, SR * 0.2) / SR)
        low += f * band
        let high = x - low - band / q
        band += f * high
        return low
    }
}

/// A stereo bus that instruments mix into at a given time.
final class Bus {
    var l: [Float], r: [Float]
    init(_ n: Int = AUDIO_N) { l = [Float](repeating: 0, count: n); r = l }
    func add(_ mono: [Float], at t: Double, gain: Double = 1, pan: Double = 0) {
        let g = Float(gain), a = (pan + 1) * Double.pi / 4
        let gl = g * Float(cos(a)), gr = g * Float(sin(a))
        let s = Int(t * SR)
        for i in 0..<mono.count {
            let j = s + i
            if j < 0 { continue }
            if j >= l.count { break }
            l[j] += mono[i] * gl; r[j] += mono[i] * gr
        }
    }
    func addStereo(_ ml: [Float], _ mr: [Float], at t: Double, gain: Double = 1) {
        let g = Float(gain), s = Int(t * SR)
        for i in 0..<ml.count {
            let j = s + i
            if j < 0 { continue }
            if j >= l.count { break }
            l[j] += ml[i] * g; r[j] += mr[i] * g
        }
    }
}

// MARK: - Reverb (Freeverb)

final class Reverb {
    struct Comb { var buf: [Double]; var idx = 0; var store = 0.0
        init(_ n: Int) { buf = [Double](repeating: 0, count: n) }
        mutating func process(_ x: Double, fb: Double, damp: Double) -> Double {
            let o = buf[idx]
            store = o * (1 - damp) + store * damp
            buf[idx] = x + store * fb
            idx += 1; if idx >= buf.count { idx = 0 }
            return o
        }
    }
    struct AllPass { var buf: [Double]; var idx = 0
        init(_ n: Int) { buf = [Double](repeating: 0, count: n) }
        mutating func process(_ x: Double) -> Double {
            let b = buf[idx]
            let o = -x + b
            buf[idx] = x + b * 0.5
            idx += 1; if idx >= buf.count { idx = 0 }
            return o
        }
    }
    static let combT = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617]
    static let apT = [556, 441, 341, 225]

    /// mono in -> stereo out
    static func process(_ input: [Float], room: Double = 0.84, damp: Double = 0.35, width: Double = 1.0) -> ([Float], [Float]) {
        let k = SR / 44100
        var cL = combT.map { Comb(Int(Double($0) * k)) }, cR = combT.map { Comb(Int(Double($0 + 23) * k)) }
        var aL = apT.map { AllPass(Int(Double($0) * k)) }, aR = apT.map { AllPass(Int(Double($0 + 23) * k)) }
        var outL = [Float](repeating: 0, count: input.count), outR = outL
        for i in 0..<input.count {
            let x = Double(input[i]) * 0.015
            var sl = 0.0, sr = 0.0
            for j in 0..<8 { sl += cL[j].process(x, fb: room, damp: damp); sr += cR[j].process(x, fb: room, damp: damp) }
            for j in 0..<4 { sl = aL[j].process(sl); sr = aR[j].process(sr) }
            outL[i] = Float(sl * (0.5 + 0.5 * width) + sr * (0.5 - 0.5 * width))
            outR[i] = Float(sr * (0.5 + 0.5 * width) + sl * (0.5 - 0.5 * width))
        }
        return (outL, outR)
    }
}

// MARK: - Drums

func kickSample(vel: Double, pitch: Double = 47) -> [Float] {
    let n = Int(0.6 * SR)
    var out = [Float](repeating: 0, count: n), ph = 0.0, rng = Rng(11)
    for i in 0..<n {
        let t = Double(i) / SR
        ph += 2 * Double.pi * (pitch + 125 * exp(-t / 0.03)) / SR
        var s = sin(ph) * exp(-t / 0.24)
        s += 0.35 * rng.next() * exp(-t / 0.004)
        out[i] = Float(tanh(s * 1.9) * vel)
    }
    return out
}

func snareSample(vel: Double, seed: UInt64 = 5) -> [Float] {
    let n = Int(0.4 * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(seed)
    var hp = Biquad(.highpass, fc: 1400, q: 0.7), bp = Biquad(.bandpass, fc: 4200, q: 0.6)
    for i in 0..<n {
        let t = Double(i) / SR
        let nz = rng.next()
        var s = hp.process(nz) * exp(-t / 0.085) * 0.9 + bp.process(nz) * exp(-t / 0.05) * 0.5
        s += sin(2 * Double.pi * 188 * t) * exp(-t / 0.055) * 0.55 + sin(2 * Double.pi * 332 * t) * exp(-t / 0.035) * 0.25
        out[i] = Float(tanh(s * 1.3) * vel)
    }
    return out
}

func clapSample(vel: Double, seed: UInt64 = 9) -> [Float] {
    let n = Int(0.35 * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(seed)
    var bp = Biquad(.bandpass, fc: 1500, q: 1.1)
    let bursts = [0.0, 0.009, 0.019, 0.031]
    for i in 0..<n {
        let t = Double(i) / SR
        var env = exp(-max(0, t - 0.031) / 0.07)
        for b in bursts where t >= b && t < b + 0.012 { env = max(env, exp(-(t - b) / 0.004)) }
        out[i] = Float(bp.process(rng.next()) * env * vel * 1.5)
    }
    return out
}

func hatSample(vel: Double, open: Bool, seed: UInt64 = 3) -> [Float] {
    let n = Int((open ? 0.34 : 0.09) * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(seed)
    var hp = Biquad(.highpass, fc: 7200, q: 0.8), bp = Biquad(.bandpass, fc: 10500, q: 1.4)
    let tau = open ? 0.11 : 0.016
    for i in 0..<n {
        let t = Double(i) / SR
        let nz = rng.next()
        out[i] = Float((hp.process(nz) * 0.7 + bp.process(nz) * 0.6) * exp(-t / tau) * vel)
    }
    return out
}

func rimSample(vel: Double) -> [Float] {
    let n = Int(0.08 * SR)
    var out = [Float](repeating: 0, count: n)
    for i in 0..<n {
        let t = Double(i) / SR
        out[i] = Float((sin(2 * Double.pi * 1760 * t) * 0.5 + sin(2 * Double.pi * 880 * t) * 0.5) * exp(-t / 0.012) * vel)
    }
    return out
}

// MARK: - Bass, keys

/// 808-style sub with glide and saturation so it still speaks on laptop speakers.
func bass808(midi: Double, dur: Double, vel: Double, glideFrom: Double? = nil) -> [Float] {
    let total = dur + 0.12
    let n = Int(total * SR)
    var out = [Float](repeating: 0, count: n), ph = 0.0
    let f = midiHz(midi), fg = glideFrom.map(midiHz) ?? f
    var lp = Biquad(.lowpass, fc: 520, q: 0.7)
    for i in 0..<n {
        let t = Double(i) / SR
        let fr = f + (fg - f) * exp(-t / 0.06) + 22 * exp(-t / 0.025)
        ph += 2 * Double.pi * fr / SR
        var env = min(1, t / 0.004) * exp(-t / (dur * 0.9 + 0.05))
        if t > dur { env *= exp(-(t - dur) / 0.03) }
        let s = tanh(sin(ph) * 2.4) * env
        out[i] = Float(lp.process(s) * vel * 0.9)
    }
    return out
}

/// Rhodes-ish electric piano: FM with a decaying index and a quick tine.
func epNote(midi: Double, dur: Double, vel: Double, seed: UInt64) -> [Float] {
    let total = dur + 1.4
    let n = Int(total * SR)
    var out = [Float](repeating: 0, count: n)
    let f = midiHz(midi)
    var rng = Rng(seed)
    let detune = 1 + rng.next() * 0.0006
    for i in 0..<n {
        let t = Double(i) / SR
        let idx = (0.9 * vel + 1.6) * exp(-t / 0.32) + 0.25
        let m = sin(2 * Double.pi * f * detune * t)
        let car = sin(2 * Double.pi * f * t + idx * m)
        let tine = 0.22 * vel * exp(-t / 0.045) * sin(2 * Double.pi * f * 14 * t)
        var env = min(1, t / 0.003) * exp(-t / 1.15)
        if t > dur { env *= exp(-(t - dur) / 0.16) }
        out[i] = Float((car + tine) * env * vel)
    }
    return out
}

// MARK: - Sax-style lead

/// A breathy, reed-like lead: additive harmonics with a formant bump, brightness that follows breath pressure,
/// delayed vibrato, scoops into notes and fall-offs out of them. It is a synthesized imitation, not a recording.
func saxNote(midi: Double, dur: Double, vel: Double, scoop: Bool = false, fall: Bool = false, vib: Double = 1, tongue: Double = 0.03, seed: UInt64 = 1) -> ([Float], [Float]) {
    let tail = fall ? 0.35 : 0.22
    let total = dur + tail
    let n = Int(total * SR)
    var out = [Float](repeating: 0, count: n), ph = 0.0, rng = Rng(seed)
    let f0 = midiHz(midi)
    let maxH = max(4, min(34, Int(9500 / f0)))
    var eq1 = Biquad(.peaking(5.5), fc: 1250, q: 0.9), eq2 = Biquad(.peaking(3.5), fc: 2700, q: 1.1), lp = Biquad(.lowpass, fc: 7800, q: 0.6)
    var breath = Biquad(.bandpass, fc: 3300, q: 0.8)
    var weights = [Double](repeating: 0, count: maxH + 1)
    var drift = 0.0
    for i in 0..<n {
        let t = Double(i) / SR
        // amplitude: tongued attack, slight swell, release (or fall-off)
        var amp = min(1, t / tongue) * (0.86 + 0.14 * min(1, t / 0.4))
        if t > dur { amp *= exp(-(t - dur) / (fall ? 0.11 : 0.07)) }
        // pitch: scoop in, vibrato after a delay, fall-off out
        var semis = 0.0
        if scoop { semis -= 1.4 * exp(-t / 0.055) }
        let vibOn = min(1, max(0, (t - 0.22) / 0.35))
        drift += (rng.next() * 0.0008 - drift * 0.0004)
        semis += vib * vibOn * 0.26 * sin(2 * Double.pi * 5.3 * t) + drift
        if fall && t > dur - 0.02 { semis -= 4.0 * min(1, (t - (dur - 0.02)) / 0.22) * min(1, (t - (dur - 0.02)) / 0.22) }
        ph += 2 * Double.pi * f0 * pow(2, semis / 12) / SR
        // brightness follows pressure
        if i % 48 == 0 {
            let press = clamp(amp * vel, 0, 1)
            let bright = 0.30 + 0.70 * press
            for h in 1...maxH {
                let hf = f0 * Double(h)
                var a = 1 / pow(Double(h), 0.82)
                a *= 1 + 1.5 * exp(-pow((hf - 1500) / 800, 2))
                a *= exp(-Double(h - 1) * (1 - bright) * 0.11)
                if hf > 4800 { a *= exp(-(hf - 4800) / 2500) }
                weights[h] = a
            }
        }
        var s = 0.0
        for h in 1...maxH { s += weights[h] * sin(Double(h) * ph) }
        s *= 0.30
        // chiff and breath
        let nz = rng.next()
        let chiff = breath.process(nz) * (0.75 * exp(-t / 0.035) + 0.07 * (1 - min(1, t / 0.4) * 0.4))
        s = (s + chiff * 0.9) * amp
        s = lp.process(eq2.process(eq1.process(tanh(s * 1.5) / 1.1)))
        out[i] = Float(s * vel)
    }
    let pan = 0.12
    let a = (pan + 1) * Double.pi / 4
    return (out.map { $0 * Float(cos(a)) }, out.map { $0 * Float(sin(a)) })
}

// MARK: - Effects

func clamp01(_ x: Double) -> Double { min(max(x, 0), 1) }

func whoosh(dur: Double, up: Bool, gain: Double = 1, seed: UInt64 = 21) -> ([Float], [Float]) {
    let n = Int((dur + 0.25) * SR)
    var l = [Float](repeating: 0, count: n), r = l, rng = Rng(seed)
    var f1 = SVF(), f2 = SVF()
    for i in 0..<n {
        let t = Double(i) / SR
        let u = clamp01(t / dur)
        let sweep = up ? u : 1 - u
        let fc = 260 * pow(26, sweep)
        let env = pow(sin(Double.pi * min(1, u * 0.999)), 1.6) * (t <= dur ? 1 : exp(-(t - dur) / 0.07))
        let nz = rng.next()
        let s = (f1.bandpass(nz, fc: fc, q: 1.4) + 0.6 * f2.bandpass(nz, fc: fc * 1.7, q: 2.0)) * env * gain * 0.55
        let pan = up ? (u * 2 - 1) : (1 - u * 2)
        let a = (pan * 0.7 + 1) * Double.pi / 4
        l[i] = Float(s * cos(a) * 1.4); r[i] = Float(s * sin(a) * 1.4)
    }
    return (l, r)
}

func riser(dur: Double, gain: Double = 1, seed: UInt64 = 31) -> ([Float], [Float]) {
    let n = Int((dur + 0.1) * SR)
    var l = [Float](repeating: 0, count: n), r = l, rng = Rng(seed)
    var f = SVF(), ph = 0.0, ph2 = 0.0
    for i in 0..<n {
        let t = Double(i) / SR
        let u = clamp01(t / dur)
        let env = pow(u, 2.1) * (t <= dur ? 1 : exp(-(t - dur) / 0.03))
        let fc = 400 * pow(30, u)
        let nz = rng.next()
        ph += 2 * Double.pi * (180 * pow(9, u)) / SR
        ph2 += 2 * Double.pi * (180 * pow(9, u) * 1.5) / SR
        let s = (f.bandpass(nz, fc: fc, q: 1.2) * 0.8 + (sin(ph) + 0.6 * sin(ph2)) * 0.18) * env * gain
        l[i] = Float(s * (0.8 + 0.2 * sin(t * 9))); r[i] = Float(s * (0.8 - 0.2 * sin(t * 9)))
    }
    return (l, r)
}

func impact(vel: Double = 1, tail: Double = 1.4) -> ([Float], [Float]) {
    let n = Int(tail * SR)
    var l = [Float](repeating: 0, count: n), r = l, rng = Rng(41)
    var ph = 0.0
    var lp = SVF()
    for i in 0..<n {
        let t = Double(i) / SR
        ph += 2 * Double.pi * (36 + 70 * exp(-t / 0.09)) / SR
        let sub = sin(ph) * exp(-t / 0.55) * 1.1
        let crash = lp.lowpass(rng.next(), fc: 9000 * exp(-t / 0.5) + 400, q: 0.9) * exp(-t / 0.35) * 0.45
        let thump = sin(2 * Double.pi * 90 * t) * exp(-t / 0.05) * 0.5
        let s = tanh((sub + crash + thump) * 1.4) * vel
        l[i] = Float(s); r[i] = Float(s * 0.97)
    }
    return (l, r)
}

func popSound(pitch: Double, vel: Double = 1) -> [Float] {
    let n = Int(0.22 * SR)
    var out = [Float](repeating: 0, count: n), ph = 0.0
    for i in 0..<n {
        let t = Double(i) / SR
        ph += 2 * Double.pi * (pitch * (1 + 0.9 * exp(-t / 0.018))) / SR
        let s = sin(ph) * exp(-t / 0.055) + 0.25 * sin(ph * 2) * exp(-t / 0.03)
        out[i] = Float(s * vel * min(1, t / 0.001))
    }
    return out
}

/// Marimba-ish pluck for the arpeggios.
func pluck(midi: Double, vel: Double = 1, len: Double = 0.45) -> [Float] {
    let n = Int(len * SR)
    var out = [Float](repeating: 0, count: n)
    let f = midiHz(midi)
    for i in 0..<n {
        let t = Double(i) / SR
        let idx = 1.8 * exp(-t / 0.05)
        let s = sin(2 * Double.pi * f * t + idx * sin(2 * Double.pi * f * 2 * t)) * exp(-t / 0.2)
        out[i] = Float((s + 0.18 * sin(2 * Double.pi * f * 4 * t) * exp(-t / 0.05)) * vel)
    }
    return out
}

func clickSound(vel: Double, tone: Double = 3200, seed: UInt64 = 7) -> [Float] {
    let n = Int(0.025 * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(seed)
    var bp = Biquad(.bandpass, fc: tone, q: 2.0)
    for i in 0..<n { out[i] = Float(bp.process(rng.next()) * exp(-Double(i) / SR / 0.004) * vel * 2.5) }
    return out
}

func stampSound(vel: Double = 1) -> [Float] {
    let n = Int(0.4 * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(51)
    var ph = 0.0
    var hp = Biquad(.highpass, fc: 1800, q: 0.7)
    for i in 0..<n {
        let t = Double(i) / SR
        ph += 2 * Double.pi * (52 + 70 * exp(-t / 0.04)) / SR
        let thump = sin(ph) * exp(-t / 0.11)
        let slap = hp.process(rng.next()) * exp(-t / 0.018) * 0.7
        out[i] = Float(tanh((thump * 1.3 + slap) * 1.2) * vel)
    }
    return out
}

func coinSound() -> [Float] {
    let n = Int(0.8 * SR)
    var out = [Float](repeating: 0, count: n)
    for i in 0..<n {
        let t = Double(i) / SR
        var s = sin(2 * Double.pi * 1318.5 * t) * exp(-t / 0.05) * min(1, t / 0.001)
        if t > 0.085 {
            let u = t - 0.085
            s += (sin(2 * Double.pi * 1975.5 * u) + 0.4 * sin(2 * Double.pi * 1975.5 * 2.76 * u)) * exp(-u / 0.22) * 0.9
        }
        out[i] = Float(s * 0.6)
    }
    return out
}

func poofSound() -> [Float] {
    let n = Int(0.3 * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(61), f = SVF()
    for i in 0..<n {
        let t = Double(i) / SR
        out[i] = Float(f.lowpass(rng.next(), fc: 5000 * exp(-t / 0.07) + 200, q: 0.9) * exp(-t / 0.09) * 1.4)
    }
    return out
}

func dingSound(vel: Double = 1) -> [Float] {
    let n = Int(0.6 * SR)
    var out = [Float](repeating: 0, count: n)
    for i in 0..<n {
        let t = Double(i) / SR
        out[i] = Float((sin(2 * Double.pi * 1568 * t) + 0.5 * sin(2 * Double.pi * 2093 * t) + 0.2 * sin(2 * Double.pi * 1568 * 2.76 * t)) * exp(-t / 0.18) * vel * 0.5)
    }
    return out
}

func vinyl(dur: Double) -> [Float] {
    let n = Int(dur * SR)
    var out = [Float](repeating: 0, count: n), rng = Rng(71), lp = Biquad(.lowpass, fc: 5500)
    var hp = Biquad(.highpass, fc: 500)
    for i in 0..<n {
        var s = rng.next() * 0.012
        if rng.next() > 0.9992 { s += rng.next() * 0.55 }
        out[i] = Float(hp.process(lp.process(s)))
    }
    return out
}

