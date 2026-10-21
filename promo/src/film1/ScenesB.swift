import Foundation
import CoreGraphics
import AppKit

// MARK: - Scene 3: limits warn early, and the gap is never hidden

func scene3(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s3 - 1.2 || t > TL.s4 + 0.1 { return }
    let L = t - TL.s3

    v.at(3, -860, -400, z: -100, alpha: clamp((L + 0.2) / 0.3)) {
        fill(c, rect(0, -17, 16, 16), P.accent)
        text(c, "LIMITS \u{00B7} AND THE GAP", 32, 0, size: 24, weight: .medium, color: P.muted, track: 0.12, mono: true)
    }
    v.at(3, -860, 0, z: -100) {
        kText(c, "Limits warn", 0, -265, size: 124, color: P.ink, t: t, t0: TL.s3 - 0.3)
        kText(c, "you early.", 0, -135, size: 124, color: P.accent, t: t, t0: TL.s3 - 0.15)
    }

    // shopping limit
    let lp = pop(t, at: TL.limitPop, rise: 70, damping: 12, freq: 14)
    v.at(3, -290, 150, z: 0, rot: lerp(-0.04, 0, lp.s), scale: lp.s, alpha: lp.a, cull: 600) {
        card(c, rect(-410, -170, 820, 340), off: 12)
        let fillU = easeOutCubic(unlerp(TL.barFill0, TL.barFill1, t))
        text(c, "Shopping", -380, -104, size: 46, weight: .semibold, color: P.ink, track: -0.02)
        text(c, "\(inr(Int(5650 * fillU))) of 7,000", 380, -104, size: 30, weight: .medium, color: P.text2, align: .right, mono: true)
        let bx = -380.0, bw = 760.0, by = -40.0, bh = 54.0
        fill(c, rect(bx, by, bw, bh), P.track)
        let frac = 5650.0 / 7000.0
        fill(c, rect(bx, by, bw * frac * fillU, bh), P.accent)
        let hu = easeInOutCubic(unlerp(TL.hatch0, TL.hatch1, t))
        if hu > 0 {
            let hx = bx + bw * frac
            let r = rect(hx, by, (bw - bw * frac) * hu, bh)
            fill(c, r, withAlpha(P.warn, 0.16))
            hatch(c, r, gap: 10, lw: 3, color: P.warn)
        }
        line(c, bx + bw, by - 16, bx + bw, by + bh + 16, P.ink, 3)
        text(c, "limit", bx + bw, by + bh + 42, size: 20, weight: .medium, color: P.muted, align: .right, mono: true)
        // 80% badge rides the end of the fill
        if t > TL.barFill1 - 0.15 {
            let b = pop(t, at: TL.barFill1 - 0.15, rise: 14)
            c.saveGState(); c.translateBy(x: CGFloat(bx + bw * frac), y: CGFloat(by + bh + 42 + b.dy)); c.scaleBy(x: CGFloat(b.s), y: CGFloat(b.s))
            fill(c, rect(-44, -24, 88, 40), P.warn)
            text(c, "80%", 0, 6, size: 26, weight: .bold, color: P.ink, align: .center, mono: true)
            c.restoreGState()
        }
        // the early warning
        let n = pop(t, at: TL.note, rise: 24)
        if n.a > 0 {
            c.saveGState(); c.translateBy(x: 0, y: CGFloat(n.dy)); c.setAlpha(CGFloat(n.a))
            fill(c, rect(-380, 96, 760, 56), withAlpha(P.warn, 0.18))
            fill(c, rect(-380, 96, 8, 56), P.warn)
            let w0 = text(c, "Hits the limit on day 23", -352, 134, size: 32, weight: .semibold, color: P.ink, track: -0.01)
            text(c, "\u{00B7} in 5 days", -352 + w0 + 14, 133, size: 26, weight: .medium, color: P.warnText, mono: true)
            c.restoreGState()
        }
    }
    // day-23 sticker
    let ds = pop(t, at: TL.note + 0.15, rise: 40, damping: 10, freq: 16)
    v.at(3, 100, -150, z: -160, rot: lerp(0.3, 0.1, ds.s), scale: ds.s, alpha: ds.a, cull: 300) {
        card(c, rect(-95, -70, 190, 140), fill: P.warn, shadow: P.ink, off: 9)
        text(c, "DAY", 0, -22, size: 24, weight: .semibold, color: P.ink, track: 0.14, align: .center, mono: true)
        text(c, "23", 0, 50, size: 84, weight: .black, color: P.ink, track: -0.04, align: .center)
    }

    // bank vs app
    let tp = pop(t, at: TL.tallyPop, rise: 70, damping: 12, freq: 14)
    v.at(3, 560, 150, z: 0, rot: lerp(0.04, 0, tp.s), scale: tp.s, alpha: tp.a, cull: 600) {
        card(c, rect(-310, -190, 620, 400), off: 12)
        text(c, "CHECK AGAINST YOUR BANK", -280, -140, size: 19, weight: .medium, color: P.muted, track: 0.1, mono: true)
        func row(_ y: Double, _ k: String, _ val: String, at t0: Double) {
            let p = pop(t, at: t0, rise: 16)
            if p.a <= 0 { return }
            c.saveGState(); c.translateBy(x: 0, y: CGFloat(p.dy)); c.setAlpha(CGFloat(p.a))
            text(c, k, -280, y, size: 30, weight: .medium, color: P.text2, mono: true)
            text(c, val, 280, y, size: 36, weight: .semibold, color: P.ink, align: .right, mono: true)
            c.restoreGState()
        }
        row(-62, "bank says", "38,251", at: TL.row1)
        row(10, "app says", "39,101", at: TL.row2)
        line(c, -280, 40, 280, 40, P.ink, 2)
        if t >= TL.gap {
            let x = t - TL.gap
            text(c, "Unaccounted", -280, 118, size: 36, weight: .semibold, color: P.ink, track: -0.02)
            let sc = 1 + 0.9 * exp(-x * 14)
            c.saveGState(); c.translateBy(x: 280, y: 118); c.scaleBy(x: CGFloat(sc), y: CGFloat(sc))
            text(c, "\u{2212}850", 0, 0, size: 64, weight: .black, color: P.danger, track: -0.02, align: .right, mono: true)
            c.restoreGState()
            let b = pop(t, at: TL.gap + 0.3, rise: 16)
            if b.a > 0 {
                c.saveGState(); c.translateBy(x: 0, y: CGFloat(b.dy)); c.setAlpha(CGFloat(b.a))
                stroke(c, rect(-280, 150, 118, 44), P.ink, 2); text(c, "Tag it", -221, 180, size: 24, weight: .semibold, color: P.ink, align: .center, mono: true)
                stroke(c, rect(-150, 150, 118, 44), P.ink, 2); text(c, "Split", -91, 180, size: 24, weight: .semibold, color: P.ink, align: .center, mono: true)
                c.restoreGState()
            }
        }
    }
}

// MARK: - Scene 4: the forecast. "The plan runs out on day 29."

private let DAILY: [Double] = [1220, 900, 1400, 700, 1250, 1900, 1500, 800, 700, 1100, 600, 850, 1300, 810, 1700, 1550, 1543, 1800, 1452, 2619, 606]
private let CUM: [Double] = { var a: [Double] = [], s = 0.0; for d in DAILY { s += d; a.append(s) }; return a }() // 26,300 on day 21
private let CX0 = -760.0, CX1 = 760.0, CBASE = 420.0, CK = 410.0 / 45000.0 // px per rupee

private func cx(_ day: Double) -> Double { CX0 + (day - 1) / 30 * (CX1 - CX0) }
private func cy(_ v: Double) -> Double { CBASE - v * CK }

func scene4(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s4 - 0.1 || t > TL.s5 + 0.1 { return }
    let L = t - TL.s4
    let flipped = t >= TL.flip

    // header: the giant 21
    let s21 = spring(L, damping: 12, freq: 18)
    v.at(4, -870, -105, z: -80, scale: lerp(1.35, 1, s21), alpha: clamp(L / 0.05)) {
        text(c, "21", 0, 0, size: 300, weight: .black, color: P.nGreen, track: -0.06)
    }
    v.at(4, -862, -395, z: -60, alpha: clamp((L - 0.1) / 0.3)) {
        fill(c, rect(0, -17, 16, 16), P.nGreen)
        text(c, "DAY OF THE MONTH \u{00B7} TODAY", 32, 0, size: 22, weight: .medium, color: P.nDim, track: 0.12, mono: true)
    }
    // headline, phase A then phase B
    v.at(4, -440, 0, z: -60) {
        let sz = 82.0
        kText(c, "At this pace", 0, -240, size: sz, color: P.white, t: t, t0: TL.axes, out: TL.flip - 0.05, outDur: 0.25)
        kText(c, "the plan runs out", 0, -150, size: sz, color: P.white, t: t, t0: TL.today, out: TL.flip - 0.05, outDur: 0.25)
        kText(c, "on day 29.", 0, -60, size: sz, color: P.nRed, t: t, t0: TL.crash, out: TL.flip - 0.05, outDur: 0.25)
        kText(c, "Spend \u{20B9}880 a day,", 0, -240, size: sz, color: P.white, t: t, t0: TL.flip + 0.05)
        kText(c, "not \u{20B9}1,250.", 0, -150, size: sz, color: P.nDim, t: t, t0: TL.flip + 0.3)
        kText(c, "and it lasts.", 0, -60, size: sz, color: P.nGreen, t: t, t0: TL.lasts)
    }
    // strike through "₹1,250" once the new pace appears
    if t > TL.flip + 0.6 {
        let u = easeOutCubic(clamp((t - TL.flip - 0.6) / 0.25))
        v.at(4, -440, -150, z: -60) { line(c, 0, -26, textWidth("not \u{20B9}1,250.", size: 82, weight: .black, track: -0.035) * u, -26, P.nRed, 6) }
    }

    // chart
    let axesU = easeOutCubic(unlerp(TL.axes, TL.axes + 0.5, t))
    v.at(4, 0, 0, z: -10, cull: 1400) {
        c.saveGState(); c.setAlpha(CGFloat(axesU))
        for k in [15000.0, 30000, 45000] {
            line(c, CX0, cy(k), CX1 + 20, cy(k), P.nLine, 1, dash: [3, 7])
            text(c, "\(Int(k / 1000))K", CX0 - 18, cy(k) + 7, size: 18, weight: .medium, color: P.nDim, align: .right, mono: true)
        }
        line(c, CX0, CBASE, CX1 + 20, CBASE, P.nDim, 1.5)
        for d in [1, 5, 10, 15, 21, 25, 31] {
            text(c, "\(d)", cx(Double(d)), CBASE + 34, size: 20, weight: d == 21 ? .bold : .medium, color: d == 21 ? P.nGreen : P.nDim, align: .center, mono: true)
        }
        text(c, "Day 1", cx(1) - 2, CBASE + 34, size: 1, color: .clear)
        c.restoreGState()
        // plan line
        line(c, CX0, cy(36000), CX0 + (CX1 - CX0 + 20) * axesU, cy(36000), P.nGreen, 3)
        text(c, "plan \u{20B9}36,000", CX0 + 6, cy(36000) - 14, size: 22, weight: .semibold, color: P.nGreen, mono: true)
    }

    // range band + projection (before the flip)
    let pu = easeInQuad(unlerp(TL.proj0, TL.crash, t))
    let redDim = flipped ? 0.18 : 1.0
    v.at(4, 0, 0, z: -10, cull: 1400) {
        if pu > 0 {
            let x0 = cx(21), y0 = cy(26300)
            let xe = cx(21 + 8 * pu), ye = cy(26300 + 1253 * 8 * pu)
            // band between the best week and the last-7-days pace, out to day 31
            let bandU = pu
            c.setFillColor(withAlpha(P.nRed, 0.10 * redDim))
            c.move(to: CGPoint(x: x0, y: y0))
            c.addLine(to: CGPoint(x: cx(21 + 10 * bandU), y: cy(26300 + 1620 * 10 * bandU)))
            c.addLine(to: CGPoint(x: cx(21 + 10 * bandU), y: cy(26300 + 880 * 10 * bandU)))
            c.closePath(); c.fillPath()
            line(c, x0, y0, xe, ye, withAlpha(P.nRed, redDim), 4, dash: [14, 9])
        }
    }
    // logged line: one point per 32nd note
    let nPts = max(0, min(21, Int((t - TL.logged0) / 0.078125) + 1))
    v.at(4, 0, 0, z: -10, cull: 1400) {
        if nPts >= 2 {
            c.setStrokeColor(P.white); c.setLineWidth(5); c.setLineJoin(.round); c.setLineCap(.round)
            c.move(to: CGPoint(x: cx(1), y: cy(CUM[0])))
            for i in 1..<nPts { c.addLine(to: CGPoint(x: cx(Double(i + 1)), y: cy(CUM[i]))) }
            c.strokePath()
        }
        if nPts >= 1 {
            let i = nPts - 1
            let k = t - (TL.logged0 + Double(i) * 0.078125)
            circle(c, cx(Double(i + 1)), cy(CUM[i]), 9 + 8 * exp(-k * 20), fill: P.white)
        }
        if nPts >= 21 {
            // today marker
            let u = clamp((t - TL.today) / 0.3)
            line(c, cx(21), cy(45000), cx(21), CBASE, withAlpha(P.nGreen, u), 2)
            c.saveGState(); c.setAlpha(CGFloat(u))
            text(c, "today \u{00B7} \u{20B9}26,300", cx(21) - 16, cy(45000) + 22, size: 22, weight: .semibold, color: P.white, align: .right, mono: true)
            c.restoreGState()
        }
    }
    // the crash: red dot, label, "2 days early"
    if t >= TL.crash {
        let x = t - TL.crash
        let p = pop(t, at: TL.crash, rise: 0, damping: 9, freq: 16)
        let redOut = 1 - easeOutCubic(clamp((t - TL.flip) / 0.25))
        v.at(4, cx(29), cy(36324), z: -10, scale: 1, alpha: max(0.28, redOut), cull: 300) {
            circle(c, 0, 0, 30 * exp(-x * 5) + 12, stroke: withAlpha(P.nRed, 0.8 * exp(-x * 4)), lw: 4)
            circle(c, 0, 0, 13 * p.s, fill: P.nRed)
            let lab = pop(t, at: TL.crash + 0.1, rise: 18)
            c.saveGState(); c.translateBy(x: 0, y: CGFloat(lab.dy)); c.setAlpha(CGFloat(lab.a * redOut))
            text(c, "plan runs out day 29", 0, 60, size: 26, weight: .bold, color: P.nRed, align: .center, mono: true)
            c.restoreGState()
        }
        // gap between day 29 and the end of the month
        let g = easeOutCubic(unlerp(TL.crash + 0.25, TL.crash + 0.55, t))
        v.at(4, 0, 0, z: -10, alpha: max(0.001, redOut), cull: 1400) {
            let y = cy(36000) - 58
            line(c, cx(29), y, cx(29) + (cx(31) - cx(29)) * g, y, P.nRed, 3)
            line(c, cx(29), y - 9, cx(29), y + 9, P.nRed, 3)
            if g > 0.98 { line(c, cx(31), y - 9, cx(31), y + 9, P.nRed, 3) }
            c.saveGState(); c.setAlpha(CGFloat(g))
            text(c, "2 days early", (cx(29) + cx(31)) / 2, y - 18, size: 22, weight: .bold, color: P.nRed, align: .center, mono: true)
            c.restoreGState()
        }
    }
    // the other line: ₹880 a day
    if t >= TL.green0 {
        let u = easeInOutCubic(unlerp(TL.green0, TL.green1, t))
        v.at(4, 0, 0, z: -10, cull: 1400) {
            let x0 = cx(21), y0 = cy(26300)
            let xe = cx(21 + 10 * u), ye = cy(26300 + 880 * 10 * u)
            line(c, x0, y0, xe, ye, P.nGreen, 6)
            circle(c, xe, ye, 11, fill: P.nGreen)
            if u > 0.99 {
                let a = pop(t, at: TL.green1, rise: 10)
                c.saveGState(); c.setAlpha(CGFloat(a.a))
                text(c, "\u{20B9}35,100 \u{00B7} lasts to day 31", xe + 6, ye + 92, size: 24, weight: .bold, color: P.nGreen, align: .right, mono: true)
                c.restoreGState()
            }
        }
    }

    // three stat cards under the chart
    let stats: [(String, String, String, Double, UInt32)] = [
        ("PLAN SURVIVES TO", "Day 31", "the last day of the month", TL.stat1, 0x2DC890),
        ("MONTH ENDS WITH", "", "between \u{20B9}6,470 and \u{20B9}13,770", TL.stat2, 0xFFFFFF),
        ("BREAKS FIRST", "Shopping", "limit hit on day 23", TL.stat3, 0xF2706A),
    ]
    for (i, st) in stats.enumerated() {
        let p = pop(t, at: st.3, rise: 60, damping: 12, freq: 14)
        v.at(4, -510 + Double(i) * 510, 640, z: 0, rot: lerp(i == 1 ? 0.0 : (i == 0 ? -0.05 : 0.05), 0, p.s), scale: p.s, alpha: p.a, cull: 500) {
            card(c, rect(-235, -105, 470, 210), fill: P.nPanel, border: P.nLine, lw: 2, shadow: C(st.4, 0.9), off: 9)
            text(c, st.0, -205, -55, size: 19, weight: .medium, color: P.nDim, track: 0.1, mono: true)
            var val = st.1
            if i == 1 { val = "\u{20B9}" + inr(Int(10040 * easeOutCubic(clamp((t - st.3) / 0.8)))) }
            text(c, val, -205, 28, size: i == 2 ? 68 : 76, weight: .black, color: C(st.4), track: -0.035)
            text(c, st.2, -205, 78, size: 22, weight: .medium, color: P.nDim, mono: true)
        }
    }
}

func easeInQuad(_ t: Double) -> Double { t * t }

// MARK: - Scene 5: the things it never sees

func scene5(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s5 - 1.2 || t > TL.s6 + 0.6 { return }
    let L = t - TL.s5

    v.at(5, -780, -400, z: -100, alpha: clamp((L + 0.2) / 0.3)) {
        fill(c, rect(0, -17, 16, 16), P.accent)
        text(c, "WHAT IT NEVER SEES", 32, 0, size: 24, weight: .medium, color: P.muted, track: 0.12, mono: true)
    }
    v.at(5, -780, 0, z: -100) {
        kText(c, "Some things", 0, -265, size: 112, color: P.ink, t: t, t0: TL.s5 - 0.3, out: TL.keeps0 - 0.1, outDur: 0.25)
        kText(c, "stay", 0, -150, size: 112, color: P.ink, t: t, t0: TL.s5 - 0.15, out: TL.keeps0 - 0.1, outDur: 0.25)
        // "blacked out." sits on its own redaction bar
        let u = easeOutExpo(unlerp(TL.s5 + 0.1, TL.s5 + 0.4, t))
        let gone = 1 - easeInCubic(clamp((t - (TL.keeps0 - 0.1)) / 0.25))
        if u > 0 && gone > 0 {
            let w = textWidth("blacked out.", size: 112, weight: .black, track: -0.035)
            c.saveGState(); c.setAlpha(CGFloat(gone))
            fill(c, rect(-12, -150, (w + 24) * u, 140), P.ink)
            c.clip(to: rect(-12, -150, (w + 24) * u, 140))
            text(c, "blacked out.", 0, -38, size: 112, weight: .black, color: P.white, track: -0.035)
            c.restoreGState()
        }
        kText(c, "Locked", 0, -150, size: 112, color: P.ink, t: t, t0: TL.keeps0)
        kText(c, "down.", 0, -38, size: 112, color: P.accent, t: t, t0: TL.keeps0 + 0.15)
    }

    // the form with its redactions
    let gone = 1 - easeInCubic(clamp((t - (TL.keeps0 - 0.15)) / 0.3))
    if gone > 0 {
        let dp = pop(t, at: TL.s5 - 0.15, rise: 80, damping: 12, freq: 14)
        v.at(5, 420, 10 + (1 - gone) * 80, z: 0, rot: lerp(0.04, 0, dp.s) + (1 - gone) * 0.15, scale: dp.s * gone, alpha: dp.a, cull: 700) {
            card(c, rect(-470, -385, 940, 770), shadow: P.ink, off: 14)
            text(c, "LBStash \u{00B7} COLLECTED FROM YOU", -430, -330, size: 20, weight: .medium, color: P.muted, track: 0.08, mono: true)
            text(c, "page 1 of 1", 430, -330, size: 20, weight: .medium, color: P.muted, align: .right, mono: true)
            line(c, -430, -300, 430, -300, P.ink, 2)
            let keys = ["Bank login", "UPI PIN", "Card number", "OTP", "Moves money"]
            let widths = [1.0, 0.38, 1.0, 0.48, 0.28]
            for i in 0..<5 {
                let y = -205 + Double(i) * 130
                text(c, keys[i], -430, y + 12, size: 34, weight: .medium, color: P.text2, mono: true)
                line(c, -430, y + 56, 430, y + 56, P.rule, 1.5)
                let bx = -150.0, maxW = 340.0
                let u = easeOutExpo(unlerp(TL.rows[i], TL.rows[i] + 0.2, t))
                // faint ghost of the value that would have been here
                fill(c, rect(bx, y - 22, maxW * widths[i], 44), withAlpha(P.track, 0.9))
                fill(c, rect(bx, y - 22, maxW * widths[i] * u, 44), P.ink)
                // stamp
                let x = t - TL.rows[i]
                if x > 0 {
                    let sc = 1 + 1.8 * exp(-x * 22)
                    c.saveGState(); c.translateBy(x: 350, y: y); c.rotate(by: -0.07); c.scaleBy(x: CGFloat(sc), y: CGFloat(sc)); c.setAlpha(CGFloat(clamp(x / 0.04)))
                    stroke(c, rect(-86, -30, 172, 60), P.danger, 4)
                    text(c, "NEVER", 0, 12, size: 36, weight: .black, color: P.danger, track: 0.06, align: .center, mono: true)
                    c.restoreGState()
                }
            }
            // big stamp
            if t >= TL.neverAll {
                let x = t - TL.neverAll
                let sc = 1 + 1.6 * exp(-x * 16)
                c.saveGState(); c.translateBy(x: 0, y: 40); c.rotate(by: -0.14); c.scaleBy(x: CGFloat(sc), y: CGFloat(sc)); c.setAlpha(CGFloat(clamp(x / 0.04)))
                fill(c, rect(-400, -76, 800, 152), withAlpha(P.white, 0.88))
                stroke(c, rect(-400, -76, 800, 152), P.danger, 9)
                text(c, "NEVER COLLECTED", 0, 26, size: 84, weight: .black, color: P.danger, track: 0.01, align: .center, mono: false)
                c.restoreGState()
            }
        }
    }

    // five locks
    let keeps: [(String, String)] = [
        ("Two-step sign-in", "Authenticator app required. Passkeys too."),
        ("Walled-off data", "Row-level security. One login per service."),
        ("Encrypted secrets", "AES-256-GCM. Argon2id. Hashed tokens."),
        ("A locked bot", "Only your Telegram account can link."),
        ("Yours to take", "Export any time. Deleted after 7 days."),
    ]
    for (i, k) in keeps.enumerated() {
        let p = pop(t, at: TL.keeps0 + Double(i) * TL.keepStep, rise: 50, damping: 12, freq: 16)
        let y = -300.0 + Double(i) * 150
        v.at(5, 420, y, z: Double(i % 2 == 0 ? -40 : 20), rot: lerp(i % 2 == 0 ? -0.05 : 0.05, 0, p.s), scale: p.s, alpha: p.a, cull: 600) {
            card(c, rect(-440, -64, 880, 128), shadow: i == 4 ? P.accent : P.ink, off: 8)
            text(c, String(format: "%02d", i + 1), -405, 12, size: 38, weight: .bold, color: P.accent, mono: true)
            text(c, k.0, -320, -6, size: 40, weight: .bold, color: P.ink, track: -0.02)
            text(c, k.1, -320, 34, size: 24, weight: .regular, color: P.muted, mono: false)
            // check mark
            c.setStrokeColor(P.accent); c.setLineWidth(7); c.setLineCap(.square)
            c.move(to: CGPoint(x: 380, y: 0)); c.addLine(to: CGPoint(x: 398, y: 20)); c.addLine(to: CGPoint(x: 424, y: -18)); c.strokePath()
        }
    }
}

// MARK: - Scene 6: eight small services

private let services: [(String, String)] = [
    ("gateway", "the only door in"), ("auth", "users, 2FA, passkeys"), ("transactions", "payments and tags"), ("planning", "plans, limits, alerts"),
    ("recurring", "repeating payments"), ("reports", "the numbers"), ("telegram", "the bot"), ("ingest", "bank messages"),
]

func scene6(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s6 - 1.2 || t > TL.s7 + 0.6 { return }
    let L = t - TL.s6

    v.at(6, -805, -400, z: -80, alpha: clamp((L + 0.2) / 0.3)) {
        fill(c, rect(0, -17, 16, 16), P.nGreen)
        text(c, "UNDER THE HOOD", 32, 0, size: 24, weight: .medium, color: P.nDim, track: 0.12, mono: true)
    }
    v.at(6, -805, 0, z: -80) {
        kText(c, "Eight small services.", 0, -250, size: 100, color: P.white, t: t, t0: TL.s6 - 0.3)
        kText(c, "One calm budget.", 0, -140, size: 100, color: P.nGreen, t: t, t0: TL.s6 - 0.1)
    }
    for (i, s) in services.enumerated() {
        let col = i % 4, row = i / 4
        let x = -603.0 + Double(col) * 402, y = 40.0 + Double(row) * 285
        let p = pop(t, at: TL.svc0 + Double(i) * TL.svcStep, rise: 50, damping: 11, freq: 17)
        v.at(6, x, y, z: Double(col % 2 == 0 ? -30 : 30), rot: lerp(i % 2 == 0 ? -0.08 : 0.08, 0, p.s), scale: p.s, alpha: p.a, cull: 400) {
            card(c, rect(-185, -125, 370, 250), fill: P.nPanel, border: P.nLine, shadow: i == 6 ? P.nGreen : C(0x000000, 0.55), off: 8)
            text(c, String(format: "%02d", i + 1), -155, -80, size: 20, weight: .medium, color: P.nDim, mono: true)
            c.saveGState(); c.translateBy(x: 0, y: -12); c.scaleBy(x: 1.35, y: 1.35)
            serviceIcon(c, s.0, color: i == 6 ? P.nGreen : P.white)
            c.restoreGState()
            text(c, s.0, 0, 78, size: 30, weight: .bold, color: P.white, align: .center, mono: true)
            text(c, s.1, 0, 108, size: 19, weight: .regular, color: P.nDim, align: .center, mono: true)
        }
    }
}

/// Line icons for the eight services, drawn in a 80 x 80 box around the origin.
func serviceIcon(_ c: CGContext, _ name: String, color: CGColor) {
    c.saveGState()
    c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(5); c.setLineCap(.square); c.setLineJoin(.miter)
    switch name {
    case "gateway":
        c.move(to: CGPoint(x: -30, y: 36)); c.addLine(to: CGPoint(x: -30, y: -4))
        c.addArc(center: CGPoint(x: 0, y: -4), radius: 30, startAngle: .pi, endAngle: 2 * .pi, clockwise: false)
        c.addLine(to: CGPoint(x: 30, y: 36)); c.strokePath()
        c.move(to: CGPoint(x: -14, y: 36)); c.addLine(to: CGPoint(x: -14, y: 6))
        c.addArc(center: CGPoint(x: 0, y: 6), radius: 14, startAngle: .pi, endAngle: 2 * .pi, clockwise: false)
        c.addLine(to: CGPoint(x: 14, y: 36)); c.strokePath()
    case "auth":
        c.move(to: CGPoint(x: 0, y: -38)); c.addLine(to: CGPoint(x: 32, y: -26)); c.addLine(to: CGPoint(x: 32, y: 6)); c.addLine(to: CGPoint(x: 0, y: 38))
        c.addLine(to: CGPoint(x: -32, y: 6)); c.addLine(to: CGPoint(x: -32, y: -26)); c.closePath(); c.strokePath()
        c.move(to: CGPoint(x: -13, y: 2)); c.addLine(to: CGPoint(x: -3, y: 12)); c.addLine(to: CGPoint(x: 15, y: -10)); c.strokePath()
    case "transactions":
        for i in 0..<3 {
            let y = -22.0 + Double(i) * 22
            c.fill(rect(-36, y - 4, 8, 8))
            c.move(to: CGPoint(x: -14, y: y)); c.addLine(to: CGPoint(x: 36, y: y)); c.strokePath()
        }
    case "planning":
        c.stroke(rect(-34, -34, 28, 28)); c.stroke(rect(6, -34, 28, 28)); c.stroke(rect(-34, 6, 28, 28)); c.fill(rect(6, 6, 28, 28))
    case "recurring":
        c.addArc(center: .zero, radius: 28, startAngle: .pi * 0.25, endAngle: .pi * 1.85, clockwise: false); c.strokePath()
        let ex = 28 * cos(Double.pi * 1.85), ey = 28 * sin(Double.pi * 1.85)
        c.move(to: CGPoint(x: ex + 14, y: ey - 4)); c.addLine(to: CGPoint(x: ex, y: ey + 16)); c.addLine(to: CGPoint(x: ex - 16, y: ey - 6)); c.closePath(); c.fillPath()
    case "reports":
        c.move(to: CGPoint(x: -36, y: -34)); c.addLine(to: CGPoint(x: -36, y: 34)); c.addLine(to: CGPoint(x: 36, y: 34)); c.strokePath()
        c.move(to: CGPoint(x: -22, y: 16)); c.addLine(to: CGPoint(x: -4, y: -2)); c.addLine(to: CGPoint(x: 10, y: 8)); c.addLine(to: CGPoint(x: 34, y: -24)); c.strokePath()
    case "telegram":
        c.move(to: CGPoint(x: -38, y: -2)); c.addLine(to: CGPoint(x: 38, y: -34)); c.addLine(to: CGPoint(x: 18, y: 36)); c.addLine(to: CGPoint(x: 2, y: 12)); c.closePath(); c.strokePath()
        c.move(to: CGPoint(x: 2, y: 12)); c.addLine(to: CGPoint(x: 38, y: -34)); c.strokePath()
    default: // ingest
        c.move(to: CGPoint(x: 0, y: -36)); c.addLine(to: CGPoint(x: 0, y: 10)); c.strokePath()
        c.move(to: CGPoint(x: -16, y: -6)); c.addLine(to: CGPoint(x: 0, y: 12)); c.addLine(to: CGPoint(x: 16, y: -6)); c.strokePath()
        c.move(to: CGPoint(x: -36, y: 8)); c.addLine(to: CGPoint(x: -36, y: 36)); c.addLine(to: CGPoint(x: 36, y: 36)); c.addLine(to: CGPoint(x: 36, y: 8)); c.strokePath()
    }
    c.restoreGState()
}

// MARK: - Scene 7: end card

func scene7(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s7 - 0.8 { return }
    let L = t - TL.s7

    // a month of days behind everything: logged days filled, the rest hatched
    for d in 1...31 {
        let idx = d - 1
        let x = Double(idx % 7 - 3) * 150, y = Double(idx / 7 - 2) * 150 - 10
        let p = pop(t, at: TL.s7 + 0.05 + Double(idx) * 0.018, rise: 0, damping: 12, freq: 16)
        v.at(7, x, y, z: 80, scale: p.s, alpha: p.a, cull: 100) {
            let r = rect(-60, -60, 120, 120)
            if d <= 21 { fill(c, r, withAlpha(P.white, 0.07)) }
            else { hatch(c, r, gap: 12, lw: 2, color: withAlpha(P.white, 0.10)); stroke(c, r, withAlpha(P.white, 0.10), 2) }
        }
    }

    // the b: stem rises, coin drops in and bounces
    let stemU = easeOutBack(clamp(L / 0.35))
    let ms = 230.0 // mark size
    v.at(7, 0, -140, z: -40, cull: 400) {
        let u = ms / 32
        c.setFillColor(P.white)
        let stemH = 22 * u * min(1.04, stemU)
        c.fill(rect(-8 * u, 11 * u - stemH, 5.5 * u, stemH))
        let ct = clamp((L - 0.18) / 0.85)
        let drop = 420 * (1 - easeOutBounce(ct))
        c.saveGState(); c.setAlpha(CGFloat(clamp((L - 0.18) / 0.04)))
        circle(c, 4.5 * u, 4.5 * u - drop, 6.5 * u, fill: P.white)
        c.restoreGState()
    }
    // wordmark
    v.at(7, 0, 150, z: -40) {
        kText(c, "LBStash", 0, 0, size: 170, weight: .semibold, color: P.white, track: -0.03, t: t, t0: TL.wordmark, dur: 0.6, align: .center)
    }
    v.at(7, 0, 150, z: -20) {
        kText(c, "See where your month ends,", 0, 78, size: 52, weight: .regular, color: P.white, track: -0.015, t: t, t0: TL.tagline, dur: 0.6, align: .center)
        kText(c, "before it ends.", 0, 142, size: 52, weight: .bold, color: P.white, track: -0.015, t: t, t0: TL.tagline + 0.3125, dur: 0.6, align: .center)
    }
    // calls to action
    let b1 = pop(t, at: TL.cta, rise: 30, damping: 12, freq: 16)
    v.at(7, -215, 430, z: -30, scale: b1.s, alpha: b1.a, cull: 400) {
        card(c, rect(-195, -48, 390, 96), fill: P.white, border: P.ink, lw: 0, shadow: P.ink, off: 8)
        text(c, "Try the demo  \u{2192}", 0, 14, size: 38, weight: .bold, color: P.accentDark, align: .center, mono: false)
    }
    let b2 = pop(t, at: TL.cta + 0.15, rise: 30, damping: 12, freq: 16)
    v.at(7, 215, 430, z: -30, scale: b2.s, alpha: b2.a, cull: 400) {
        stroke(c, rect(-195, -48, 390, 96), P.white, 4)
        text(c, "Create account", 0, 13, size: 36, weight: .semibold, color: P.white, align: .center, mono: false)
    }
    let ur = pop(t, at: TL.cta + 0.4, rise: 12)
    v.at(7, 0, 520, z: -30, alpha: ur.a, cull: 300) {
        text(c, "lbstash.site", 0, 0, size: 34, weight: .medium, color: withAlpha(P.white, 0.85), track: 0.06, align: .center, mono: true)
    }
}

func easeOutBack(_ t: Double) -> Double {
    let c1 = 1.70158, c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)
}

func easeOutBounce(_ x: Double) -> Double {
    let n1 = 7.5625, d1 = 2.75
    if x < 1 / d1 { return n1 * x * x }
    if x < 2 / d1 { let y = x - 1.5 / d1; return n1 * y * y + 0.75 }
    if x < 2.5 / d1 { let y = x - 2.25 / d1; return n1 * y * y + 0.9375 }
    let y = x - 2.625 / d1; return n1 * y * y + 0.984375
}
