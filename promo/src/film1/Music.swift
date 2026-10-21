import Foundation

// 96 BPM, A minor. Chord loop: Am9 | Fmaj7 | Dm9 | E7. Bar = 2.5 s, step = 1/16 note = 0.15625 s.

private let SWING = 0.12 * S16

/// Time of a (possibly fractional) 16th-note step in a bar, with MPC-style swing on the off-16ths.
func stepTime(_ bar: Int, _ step: Double) -> Double {
    let whole = floor(step)
    let sw = Int(whole) % 2 == 1 ? SWING : 0
    return Double(bar) * BAR + step * S16 + sw
}

// chord indices: 0 Am9, 1 Fmaj7, 2 Dm9, 3 E7
private func chordAt(_ bar: Int, _ step: Int) -> Int {
    switch bar {
    case 0: return 2
    case 1: return 3
    case 14, 15: return step < 8 ? 2 : 3
    case 16, 17: return 0
    case 12: return 0
    case 13: return 1
    default: return [0, 1, 2, 3][(bar - 2 + 4) % 4]
    }
}
private let voicings: [[Double]] = [
    [52, 55, 59, 60, 64],      // Am9: E3 G3 B3 C4 E4
    [53, 57, 60, 64, 67],      // Fmaj7(9)
    [50, 57, 60, 64, 65],      // Dm9
    [52, 56, 59, 62, 67],      // E7#9
]
private let bassRoot: [Double] = [33, 29, 38, 40]
private let bassFifth: [Double] = [40, 36, 33, 35]

// MARK: - Sax lines, keyed by chord (step, length in steps, midi)

typealias Line = [(Int, Int, Double)]
private let p1: [Line] = [
    [(2, 2, 72), (4, 3, 76), (8, 2, 74), (10, 2, 72), (12, 4, 69)],
    [(2, 2, 69), (4, 2, 72), (6, 2, 76), (8, 4, 74), (12, 2, 72), (14, 2, 69)],
    [(2, 2, 77), (4, 2, 76), (6, 2, 74), (8, 3, 72), (11, 1, 69), (12, 4, 67)],
    [(0, 2, 71), (2, 2, 68), (4, 2, 71), (6, 2, 74), (8, 5, 76)],
]
private let p2: [Line] = [
    [(0, 2, 81), (2, 2, 79), (4, 2, 76), (6, 2, 72), (8, 4, 76), (12, 2, 79), (14, 2, 76)],
    [(0, 3, 77), (3, 1, 76), (4, 4, 72), (8, 2, 69), (10, 2, 72), (12, 4, 77)],
    [(0, 2, 74), (2, 2, 77), (4, 4, 81), (8, 2, 79), (10, 2, 77), (12, 4, 74)],
    [(0, 2, 76), (2, 2, 74), (4, 2, 71), (6, 2, 68), (8, 4, 71), (12, 4, 76)],
]

private struct SaxPlan { var line: Line; var cut: Int = 16 }

private func saxPlan(_ bar: Int) -> SaxPlan? {
    let c = chordAt(bar, 0)
    switch bar {
    case 0: return SaxPlan(line: [(4, 12, 69)])
    case 1: return SaxPlan(line: [(0, 6, 71), (8, 6, 68)])
    case 2...5: return SaxPlan(line: p1[c])
    case 6: return SaxPlan(line: p2[c])
    case 7: return SaxPlan(line: Array(p2[c].filter { $0.0 < 10 }), cut: 12)
    case 8: return nil
    case 9: return SaxPlan(line: [(0, 12, 76)], cut: 12)
    case 10, 11: return SaxPlan(line: p2[c])
    case 12, 13: return nil
    case 14: return SaxPlan(line: [(0, 2, 69), (2, 2, 72), (4, 2, 74), (6, 2, 76), (8, 2, 79), (10, 2, 81), (12, 4, 84)])
    case 15: return SaxPlan(line: [(4, 2, 81), (6, 2, 79), (8, 2, 76), (10, 2, 74), (12, 4, 71)])
    case 16: return SaxPlan(line: [(0, 4, 81), (4, 4, 79), (8, 2, 76), (10, 2, 79), (12, 4, 81)])
    case 17: return SaxPlan(line: [(0, 18, 81)])
    default: return nil
    }
}

private let pentatonic: [Double] = [0, 3, 5, 7, 10] // A minor pentatonic degrees
private func snapPentatonic(_ m: Double) -> Double {
    var best = m, bd = 99.0
    for oct in 0..<10 { for d in pentatonic {
        let c = 33 + Double(oct) * 12 + d // A1 + ...
        if abs(c - m) < bd { bd = abs(c - m); best = c }
    } }
    return best
}

// MARK: - The arrangement

final class Song {
    let drums = Bus(), bass = Bus(), keys = Bus(), sax = Bus(), sfx = Bus(), roll = Bus()
    var revSend = [Float](repeating: 0, count: AUDIO_N)
    var rng = Rng(2024)

    func send(_ mono: [Float], at t: Double, gain: Double) {
        let s = Int(t * SR)
        for i in 0..<mono.count { let j = s + i; if j >= 0 && j < revSend.count { revSend[j] += mono[i] * Float(gain) } }
    }
    func sendStereo(_ l: [Float], _ r: [Float], at t: Double, gain: Double) {
        let s = Int(t * SR)
        for i in 0..<l.count { let j = s + i; if j >= 0 && j < revSend.count { revSend[j] += (l[i] + r[i]) * 0.5 * Float(gain) } }
    }
    func jitter() -> Double { rng.next() * 0.003 }
    func hv(_ v: Double) -> Double { clamp(v * (1 + rng.next() * 0.08), 0, 1.2) }

    // drum helpers
    func kick(_ t: Double, _ v: Double) { drums.add(kickSample(vel: hv(v)), at: t + jitter() * 0.3, gain: 1.15) }
    func snare(_ t: Double, _ v: Double, bus: Bus? = nil, clap: Bool = true) {
        (bus ?? drums).add(snareSample(vel: hv(v), seed: UInt64(t * 1000) & 0xFFFF | 1), at: t + jitter(), gain: 0.95, pan: 0.02)
        if clap && v > 0.5 { (bus ?? drums).add(clapSample(vel: hv(v * 0.45), seed: UInt64(t * 777) & 0xFFFF | 1), at: t + jitter(), gain: 0.8, pan: -0.06) }
        send(snareSample(vel: v * 0.5, seed: 3), at: t, gain: 0.25)
    }
    func hat(_ t: Double, _ v: Double, open: Bool = false) {
        drums.add(hatSample(vel: hv(v), open: open, seed: UInt64(t * 913) & 0xFFFF | 1), at: t + jitter(), gain: 0.5, pan: 0.18)
    }
    func note808(_ t: Double, _ midi: Double, _ dur: Double, _ v: Double, from: Double? = nil) { bass.add(bass808(midi: midi, dur: dur, vel: v, glideFrom: from), at: t, gain: 0.95) }
    func chord(_ t: Double, _ ch: Int, dur: Double, vel: Double, strum: Double = 0.010) {
        for (i, m) in voicings[ch].enumerated() {
            let n = epNote(midi: m, dur: dur, vel: vel * (0.8 + 0.2 * Double(i % 2)), seed: UInt64(i + 1) &* UInt64(t * 100 + 7))
            let pan = -0.35 + 0.7 * Double(i) / 4
            keys.add(n, at: t + Double(i) * strum, gain: 0.38, pan: pan)
            send(n, at: t + Double(i) * strum, gain: 0.35)
        }
    }
    func saxPlay(_ t: Double, _ midi: Double, dur: Double, vel: Double, scoop: Bool, fall: Bool, vib: Double, tongue: Double = 0.03) {
        let (l, r) = saxNote(midi: midi, dur: dur, vel: vel, scoop: scoop, fall: fall, vib: vib, tongue: tongue, seed: UInt64(midi * 31 + t * 10) & 0xFFFF | 1)
        sax.addStereo(l, r, at: t, gain: 0.50)
        sendStereo(l, r, at: t, gain: 0.42)
    }

    func compose() {
        for bar in 0..<18 { composeBar(bar) }
    }

    private func composeBar(_ bar: Int) {
        let t0 = Double(bar) * BAR
        let cutStep: Int = (bar == 7 || bar == 9) ? 12 : 16
        let ch = chordAt(bar, 0)

        // ---- drums
        func K(_ s: Double, _ v: Double) { if Int(s) < cutStep { kick(stepTime(bar, s), v) } }
        func S(_ s: Double, _ v: Double) { if Int(s) < cutStep { snare(stepTime(bar, s), v) } }
        func H(_ s: Double, _ v: Double, open: Bool = false) { if Int(s) < cutStep { hat(stepTime(bar, s), v, open: open) } }
        func roll(_ from: Double, _ to: Double, _ stepSize: Double, _ v0: Double, _ v1: Double) {
            var s = from
            while s < to {
                let v = lerp(v0, v1, (s - from) / (to - from))
                snare(stepTime(bar, s), v, bus: self.roll, clap: false)
                s += stepSize
            }
        }
        let hatVel: [Double] = [0.62, 0.0, 0.40, 0.0, 0.58, 0.0, 0.42, 0.0, 0.62, 0.0, 0.40, 0.0, 0.58, 0.0, 0.46, 0.0]

        switch bar {
        case 0:
            for s in [8, 10, 12, 14] { H(Double(s), 0.12 + Double(s - 8) * 0.03) }
        case 1:
            K(0, 0.85); K(10, 0.6)
            for s in stride(from: 0, to: 12, by: 2) { H(Double(s), 0.25 + Double(s) * 0.025) }
            roll(12, 16, 1, 0.4, 0.95)
        case 2, 3, 4, 5, 10, 11, 14, 15, 16:
            let peak = bar == 10 || bar == 11 || bar == 16
            let build = bar == 14
            if build { for s in [0, 4, 8, 12] { K(Double(s), 0.8) } } else { K(0, 1.0); K(7, 0.55); K(10, 0.85); if peak || bar % 4 == 3 { K(14, 0.5) } }
            S(4, 0.9); S(12, 0.9)
            if bar % 2 == 0 { S(7, 0.2) }
            if peak {
                for s in 0..<16 { H(Double(s), [0.62, 0.22, 0.4, 0.22, 0.58, 0.22, 0.42, 0.26, 0.62, 0.22, 0.4, 0.22, 0.58, 0.22, 0.46, 0.3][s]) }
                H(6, 0.42, open: true); H(14, 0.45, open: true)
            } else {
                for s in 0..<16 where hatVel[s] > 0 { H(Double(s), hatVel[s]) }
                H(15, 0.2)
                if bar % 2 == 1 { H(14, 0.5, open: true) }
            }
            if bar == 5 || bar == 15 || bar == 11 || bar == 14 { roll(12, 16, 0.5, 0.35, 0.95) }
            if bar == 11 { roll(11.5, 16, 0.5, 0.35, 0.95) }
        case 6:
            K(0, 1.0); K(3, 0.45); K(7, 0.6); K(10, 0.85); K(14, 0.55); S(4, 0.9); S(12, 0.9); S(9, 0.2)
            for s in 0..<16 { H(Double(s), [0.62, 0.22, 0.4, 0.22, 0.58, 0.22, 0.42, 0.26, 0.62, 0.22, 0.4, 0.22, 0.58, 0.22, 0.46, 0.3][s]) }
            H(6, 0.42, open: true); H(14, 0.45, open: true)
        case 7:
            K(0, 1.0); K(7, 0.55); K(10, 0.85); S(4, 0.9)
            for s in 0..<12 { H(Double(s), [0.62, 0.22, 0.4, 0.22, 0.58, 0.22, 0.42, 0.26, 0.62, 0.22, 0.4, 0.22][s]) }
            roll(12, 16, 0.5, 0.3, 1.0)
        case 8:
            K(0, 1.1); K(10, 0.75)
            for s in [8, 12] { drums.add(rimSample(vel: 0.45), at: stepTime(bar, Double(s)), gain: 0.8) }
            for s in [8, 10, 12, 14] { H(Double(s), 0.3) }
        case 9:
            K(0, 0.9); K(6, 0.6); K(10, 0.7); S(4, 0.5)
            for s in stride(from: 0, to: 12, by: 2) { H(Double(s), 0.3 + Double(s) * 0.02) }
            drums.add(rimSample(vel: 0.4), at: stepTime(bar, 8), gain: 0.8)
        case 12, 13:
            K(0, 1.0); if bar == 12 { K(10, 0.8) } else { K(8, 0.9); K(11, 0.6) }
            for s in stride(from: 0, to: 16, by: 2) { H(Double(s), 0.22 + (s % 4 == 0 ? 0.08 : 0)) }
        case 17:
            K(0, 1.0)
        default: break
        }

        // ---- bass (808)
        let r = bassRoot[ch], fth = bassFifth[ch]
        switch bar {
        case 0: break
        case 1: note808(stepTime(bar, 0), r, 1.2, 0.7)
        case 8: note808(stepTime(bar, 0), 33, 2.2, 1.0)
        case 9: note808(stepTime(bar, 0), r, 1.4, 0.85); note808(stepTime(bar, 10), fth, 0.3, 0.6)
        case 12, 13: note808(stepTime(bar, 0), r, 2.1, 0.95, from: r + 3)
        case 17: note808(stepTime(bar, 0), 33, 1.3, 0.9)
        default:
            note808(stepTime(bar, 0), r, 5 * S16, 1.0)
            note808(stepTime(bar, 7), r + 12, 2 * S16, 0.55)
            if cutStep > 10 { note808(stepTime(bar, 10), fth, 4 * S16, 0.85, from: r) }
        }

        // ---- keys
        switch bar {
        case 0: chord(t0, ch, dur: 2.2, vel: 0.7, strum: 0.03)
        case 1: chord(t0, ch, dur: 1.2, vel: 0.65); chord(stepTime(bar, 8), ch, dur: 1.2, vel: 0.7)
        case 8: chord(t0, ch, dur: 2.3, vel: 0.9, strum: 0.02)
        case 9: chord(t0, ch, dur: 1.8, vel: 0.75); chord(stepTime(bar, 10), ch, dur: 0.5, vel: 0.7)
        case 12, 13: chord(t0, ch, dur: 2.2, vel: 0.65, strum: 0.04); chord(stepTime(bar, 10), ch, dur: 0.4, vel: 0.45)
        case 14, 15:
            chord(t0, chordAt(bar, 0), dur: 1.1, vel: 0.8); chord(stepTime(bar, 8), chordAt(bar, 8), dur: 1.1, vel: 0.8)
        case 17: chord(t0, ch, dur: 1.4, vel: 0.85, strum: 0.02)
        default:
            chord(t0, ch, dur: 6 * S16, vel: 0.8)
            chord(stepTime(bar, 6), ch, dur: 2 * S16, vel: 0.55)
            if cutStep > 10 { chord(stepTime(bar, 10), ch, dur: 4 * S16, vel: 0.7) }
        }

        // ---- sax
        if let plan = saxPlan(bar) {
            for (i, nline) in plan.line.enumerated() where nline.0 < plan.cut {
                let st = stepTime(bar, Double(nline.0))
                var dur = Double(min(nline.1, plan.cut - nline.0)) * S16 * 0.96
                var fall = i == plan.line.count - 1 && nline.1 >= 4
                let afterRest = i == 0 || (plan.line[i - 1].0 + plan.line[i - 1].1) < nline.0
                var vel = 0.88
                var vib = nline.1 >= 4 ? 1.0 : 0.5
                if bar == 17 { dur = 1.9; fall = true; vib = 1.2; vel = 0.95 }
                if bar == 0 { vel = 0.6; vib = 0.8 }
                if bar == 9 { vel = 0.85; vib = 1.5 }
                if bar >= 10 && bar <= 11 { vel = 0.97 }
                saxPlay(st, nline.2, dur: dur, vel: vel, scoop: afterRest, fall: fall, vib: vib, tongue: nline.1 <= 1 ? 0.012 : 0.03)
            }
        }
    }

    // MARK: sound design, locked to the video cues in TL

    func design() {
        func pop(_ t: Double, _ pitch: Double, _ v: Double = 0.5, pan: Double = 0) {
            let p = popSound(pitch: pitch, vel: v); sfx.add(p, at: t, gain: 0.55, pan: pan); send(p, at: t, gain: 0.25)
        }
        func swoosh(_ t0: Double, _ dur: Double, up: Bool, g: Double = 0.8) {
            let (l, r) = whoosh(dur: dur, up: up, gain: g, seed: UInt64(t0 * 97) & 0xFFFF | 1); sfx.addStereo(l, r, at: t0, gain: 0.7)
        }
        func hit(_ t: Double, _ v: Double, tail: Double = 1.4) {
            let (l, r) = impact(vel: v, tail: tail); sfx.addStereo(l, r, at: t, gain: 0.95); sendStereo(l, r, at: t, gain: 0.1)
        }
        func click(_ t: Double, _ v: Double = 0.4, tone: Double = 3200) { sfx.add(clickSound(vel: v, tone: tone, seed: UInt64(t * 1234) & 0xFFFF | 1), at: t, gain: 0.6, pan: 0.15) }
        func stamp(_ t: Double, _ v: Double = 0.9) { let s = stampSound(vel: v); sfx.add(s, at: t, gain: 0.9); send(s, at: t, gain: 0.12) }
        func pl(_ t: Double, _ m: Double, _ v: Double = 0.5, pan: Double = 0) { let p = pluck(midi: m, vel: v); sfx.add(p, at: t, gain: 0.6, pan: pan); send(p, at: t, gain: 0.4) }
        func rise(_ t0: Double, _ dur: Double, g: Double = 0.7) { let (l, r) = riser(dur: dur, gain: g, seed: UInt64(t0 * 53) & 0xFFFF | 1); sfx.addStereo(l, r, at: t0, gain: 0.8) }

        // Scene 0: slam, counting ticks, the question
        hit(0.0, 1.0, tail: 2.0)
        for k in 1...21 { let m = snapPentatonic(45 + 27 * Double(k - 1) / 20); pl(TL.tick(k), m, 0.35 + 0.01 * Double(k), pan: -0.3 + 0.6 * Double(k) / 21) }
        hit(2.5, 0.55, tail: 1.0)
        for (i, w) in TL.words.enumerated() { pop(w, [440, 523, 659][i], 0.5) }
        rise(3.75, 1.25, g: 0.9)
        swoosh(4.3, 0.7, up: true, g: 1.0)
        hit(5.0, 0.9, tail: 1.6)
        // Scene 1: telegram
        pop(TL.s1 + 0.12, 330, 0.5)
        pop(TL.stopwatch, 660, 0.5)
        var tk = TL.typeStart; while tk < TL.typeEnd { click(tk, 0.35, tone: 2600 + 300 * Double((Int(tk * 100)) % 3)); tk += 0.09 }
        swoosh(TL.send, 0.28, up: true, g: 0.6)
        pop(TL.amountCard, 523, 0.55, pan: -0.3)
        pl(TL.reply, 76, 0.55); pl(TL.reply + 0.08, 81, 0.5)
        var ct = TL.reply; while ct < TL.countEnd { click(ct, 0.2, tone: 4200); ct += 0.07 }
        sfx.add(poofSound(), at: TL.deleteMsg, gain: 0.7)
        pop(TL.deletedCard, 392, 0.55, pan: 0.3)
        pop(TL.msg2, 440, 0.5); pl(TL.reply2, 79, 0.5); pl(TL.reply2 + 0.08, 84, 0.45)
        swoosh(9.3, 0.7, up: true, g: 1.0)
        hit(10.0, 0.6, tail: 1.2)
        // Scene 2
        pop(TL.smsPop, 349, 0.5)
        var sm = TL.smsType0; while sm < TL.smsType1 { click(sm, 0.25, tone: 2400); sm += 0.055 }
        click(TL.arrow, 0.6, tone: 1500)
        sfx.add(coinSound(), at: TL.salary, gain: 0.8); pop(TL.salary, 523, 0.5)
        for i in 0..<6 { click(TL.salary + 0.12 + Double(i) * 0.06, 0.3, tone: 5200 + Double(i) * 300) }
        pop(TL.rentPop, 392, 0.5, pan: 0.3)
        pl(TL.stem1, 64, 0.6); pl(TL.stem1 + 0.15, 71, 0.55); pl(TL.stem2, 69, 0.55)
        pop(TL.upiPop, 330, 0.5)
        stamp(TL.tagStamp, 0.8); pl(TL.remembered, 79, 0.5); pl(TL.remembered + 0.1, 84, 0.45)
        swoosh(14.3, 0.7, up: false, g: 1.0)
        hit(15.0, 0.55, tail: 1.2)
        // Scene 3
        pop(TL.limitPop, 392, 0.5, pan: -0.3)
        for i in 0..<10 { pl(TL.barFill0 + Double(i) * 0.08, snapPentatonic(57 + Double(i) * 1.5), 0.25) }
        sfx.add(dingSound(vel: 0.8), at: TL.barFill1 - 0.15, gain: 0.55)
        var hh = TL.hatch0; while hh < TL.hatch1 { click(hh, 0.25, tone: 5600); hh += 0.06 }
        pop(TL.note, 523, 0.55); pop(TL.note + 0.15, 659, 0.5, pan: 0.2)
        pop(TL.tallyPop, 349, 0.5, pan: 0.3)
        click(TL.row1, 0.7, tone: 1800); click(TL.row2, 0.7, tone: 1800)
        stamp(TL.gap, 1.0); pop(TL.gap + 0.3, 440, 0.45)
        rise(19.0, 1.0, g: 0.9)
        // Scene 4: forecast
        hit(TL.slam21, 1.15, tail: 2.2)
        pop(TL.axes, 523, 0.45)
        for i in 0..<21 { pl(TL.logged0 + Double(i) * 0.078125, snapPentatonic(57 + 24 * Double(i) / 20), 0.38 + 0.01 * Double(i), pan: -0.4 + 0.8 * Double(i) / 20) }
        sfx.add(dingSound(vel: 0.9), at: TL.today, gain: 0.6)
        rise(TL.proj0, TL.crash - TL.proj0, g: 1.0)
        hit(TL.crash, 1.2, tail: 2.0); sfx.add(stampSound(vel: 1.0), at: TL.crash, gain: 0.8)
        swoosh(TL.flip - 0.05, 0.55, up: true, g: 0.9)
        pop(TL.flip + 0.05, 659, 0.5)
        let up8: [Double] = [69, 72, 74, 76, 79, 81, 84, 88]
        for (i, m) in up8.enumerated() { pl(TL.green0 + Double(i) * S16, m, 0.45, pan: -0.3 + 0.6 * Double(i) / 7) }
        pop(TL.lasts, 784, 0.55); pop(TL.stat1, 523, 0.55, pan: -0.3); pop(TL.stat2, 659, 0.55); pop(TL.stat3, 784, 0.55, pan: 0.3)
        var cu = TL.stat2; while cu < TL.stat2 + 0.8 { click(cu, 0.25, tone: 4800); cu += 0.06 }
        swoosh(29.3, 0.7, up: true, g: 1.0)
        hit(30.0, 0.8, tail: 1.6)
        // Scene 5
        for t in TL.rows { swoosh(t - 0.12, 0.22, up: true, g: 0.4); stamp(t, 0.85) }
        hit(TL.neverAll, 0.95, tail: 1.6); stamp(TL.neverAll, 1.0)
        let keepN: [Double] = [69, 72, 74, 76, 81]
        for i in 0..<5 { let t = TL.keeps0 + Double(i) * TL.keepStep; pop(t, midiHz(keepN[i] - 12) , 0.5); pl(t + 0.03, keepN[i], 0.5, pan: -0.3 + 0.15 * Double(i)) }
        swoosh(36.8, 0.7, up: true, g: 1.0)
        hit(37.5, 0.55, tail: 1.2)
        // Scene 6
        let svcN: [Double] = [69, 72, 74, 76, 79, 81, 84, 88]
        for i in 0..<8 { let t = TL.svc0 + Double(i) * TL.svcStep; pop(t, 392 + Double(i) * 30, 0.4, pan: -0.5 + Double(i) * 0.14); pl(t, svcN[i], 0.5, pan: -0.5 + Double(i) * 0.14) }
        rise(38.75, 1.25, g: 1.0)
        swoosh(39.4, 0.62, up: true, g: 1.0)
        // Scene 7: end card
        hit(TL.logo, 1.2, tail: 2.6)
        for (i, bt) in [0.364, 0.727, 0.909, 1.0].enumerated() {
            let t = TL.s7 + 0.18 + 0.85 * bt
            let p = popSound(pitch: 1480 - Double(i) * 160, vel: 0.5 * (1 - Double(i) * 0.2)); sfx.add(p, at: t, gain: 0.5, pan: 0.1)
        }
        swoosh(TL.wordmark - 0.1, 0.45, up: true, g: 0.7)
        pop(TL.tagline, 659, 0.5); pop(TL.tagline + 0.3125, 784, 0.55)
        pop(TL.cta, 523, 0.5, pan: -0.2); pop(TL.cta + 0.15, 659, 0.5, pan: 0.2); click(TL.cta + 0.4, 0.5, tone: 2200)
        // final button: chord + crash on the last hit
        let finalT = stepTime(17, 8)
        hit(finalT, 1.0, tail: 2.8)
        chord(finalT, 0, dur: 2.2, vel: 1.0, strum: 0.015)
        note808(finalT, 33, 2.2, 1.0)
        kick(finalT, 1.0); snare(finalT, 0.8)
        let crash = hatSample(vel: 0.9, open: true, seed: 99); drums.add(crash, at: finalT, gain: 0.4)
    }
}
