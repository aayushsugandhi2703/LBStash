import Foundation
import CoreGraphics
import AppKit

// MARK: - Shared timing (video and audio both read these so every pop has a matching sound)

enum TL {
    // Scene starts (bar boundaries: bar = 2.5 s)
    static let s0 = 0.0, s1 = 5.0, s2 = 10.0, s3 = 15.0, s4 = 20.0, s5 = 30.0, s6 = 37.5, s7 = 40.0

    // Scene 0: cold open
    static func tick(_ k: Int) -> Double { 0.625 + 1.875 * (1 - pow(1 - Double(k - 1) / 20, 1.5)) }
    static let words = [2.5, 3.125, 3.75]

    // Scene 1: Telegram
    static let stopwatch = 5.35, typeStart = 5.55, typeEnd = 6.35, send = 6.5, amountCard = 6.6
    static let dotsStart = 6.75, reply = 7.1, countEnd = 7.75, deleteMsg = 8.1, deletedCard = 8.2
    static let msg2 = 8.75, reply2 = 9.05

    // Scene 2: salary, rent, unknown payee
    static let smsPop = 10.1, smsType0 = 10.3, smsType1 = 11.0, arrow = 11.05, salary = 11.25
    static let rentPop = 11.9, stem1 = 12.2, stem2 = 12.65, upiPop = 13.0, tagStamp = 13.7, remembered = 14.0

    // Scene 3: limits and the gap
    static let limitPop = 15.25, barFill0 = 15.6, barFill1 = 16.4, hatch0 = 16.5, hatch1 = 17.1, note = 17.2
    static let tallyPop = 17.6, row1 = 18.0, row2 = 18.3, gap = 18.65

    // Scene 4: forecast climax
    static let slam21 = 20.0, axes = 20.3125, logged0 = 20.9375, today = 22.5, proj0 = 22.5, crash = 24.375
    static let flip = 25.0, green0 = 25.3125, green1 = 26.5625, lasts = 26.25, stat1 = 26.875, stat2 = 27.5, stat3 = 28.125

    // Scene 5: privacy
    static let rows = (0..<5).map { 30.625 + Double($0) * 0.625 }
    static let neverAll = 33.75, keeps0 = 34.375, keepStep = 0.3125

    // Scene 6: services montage
    static let svc0 = 37.8125, svcStep = 0.15625

    // Scene 7: end card
    static let logo = 40.0, wordmark = 40.3, tagline = 41.25, cta = 42.5
}

let GRID_ALPHA = 0.9

// MARK: - Backdrop: stage colours, hairline grid

func drawBackdrop(_ v: View) {
    for i in 0..<stageCenters.count {
        let d = hypot(v.cam.x - stageCenters[i].0, v.cam.y - stageCenters[i].1)
        if d > 4400 { continue }
        let dark = [0, 4, 6].contains(i)
        let gridColor: CGColor = dark ? C(0xFFFFFF, 0.05) : (i == 2 || i == 7 ? C(0xFFFFFF, 0.10) : C(0x0E0E10, 0.045))
        v.at(i, 0, 0, z: 0, cull: 4000) {
            fill(v.c, rect(-stageHalf, -stageHalf, stageHalf * 2, stageHalf * 2), stageColors[i])
            v.c.setStrokeColor(gridColor); v.c.setLineWidth(1.5)
            var g = -2520.0
            while g <= 2520 {
                v.c.move(to: CGPoint(x: g, y: -stageHalf)); v.c.addLine(to: CGPoint(x: g, y: stageHalf))
                v.c.move(to: CGPoint(x: -stageHalf, y: g)); v.c.addLine(to: CGPoint(x: stageHalf, y: g))
                g += 120
            }
            v.c.strokePath()
        }
    }
}

// MARK: - Whip streaks: colour blocks scattered in the gap between two stages, so a fast camera move reads as streaks of colour

private let whipPairs: [(Int, Int)] = [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (6, 7)]
private let streakColors: [CGColor] = [P.accent, P.ink, P.white, P.nGreen, P.accentLight, P.warn, P.white, P.accentDark]

func drawWhipStreaks(_ v: View) {
    for (pi, pair) in whipPairs.enumerated() {
        let a = stageCenters[pair.0], b = stageCenters[pair.1]
        let mx = (a.0 + b.0) / 2, my = (a.1 + b.1) / 2
        if hypot(v.cam.x - mx, v.cam.y - my) > 3400 { continue }
        let horizontal = abs(b.0 - a.0) > abs(b.1 - a.1)
        for k in 0..<13 {
            let h = hash01(pi * 31 + k * 7)
            let along = (hash01(pi * 17 + k * 3 + 1) - 0.5) * 800       // spread along the travel direction (kept well clear of both stages)
            let across = (hash01(pi * 13 + k * 5 + 2) - 0.5) * 1500     // spread across it
            let len = 400 + hash01(pi * 11 + k) * 400, thick = 40 + hash01(pi * 5 + k * 9) * 130
            let z = -260 + hash01(pi * 3 + k * 11) * 700
            let color = streakColors[(pi + k) % streakColors.count]
            v.at(-1, mx + (horizontal ? along : across), my + (horizontal ? across : along), z: z, cull: 1200, stageOverride: true) {
                _ = h
                fill(v.c, horizontal ? rect(-len / 2, -thick / 2, len, thick) : rect(-thick / 2, -len / 2, thick, len), color)
            }
        }
    }
}

// MARK: - Scene 0: "It's day 21. Where's your month going?"

func scene0(_ v: View) {
    let c = v.c, t = v.t
    if t > 6.0 { return }
    // label
    v.at(0, -800, -430, z: -30, alpha: clamp((t - 0.15) / 0.4)) {
        fill(c, rect(0, -17, 16, 16), P.nGreen)
        text(c, "A PRIVATE BUDGET TRACKER", 32, 0, size: 24, weight: .medium, color: P.nDim, track: 0.12, mono: true)
    }
    // "It's day" slams in on the first frame
    let sl = spring(t, damping: 13, freq: 20)
    v.at(0, -806, -190, z: -50, scale: lerp(1.55, 1, sl), alpha: clamp(t / 0.05)) {
        text(c, "It\u{2019}s day", 0, 0, size: 140, weight: .black, color: P.white, track: -0.045)
    }
    // the counter: 1 ... 21, ticking faster and faster
    if t >= TL.tick(1) {
        var n = 1
        for k in 1...21 where TL.tick(k) <= t { n = k }
        let since = t - TL.tick(n)
        var punch = 1 + 0.05 * exp(-since * 22)
        if n == 21 { punch += 0.20 * exp(-since * 9) * cos(since * 14) }
        v.at(0, -820, 170, z: -60, scale: punch) {
            text(c, "\(n)", 0, 0, size: 420, weight: .black, color: P.nGreen, track: -0.06)
        }
    }
    // month grid: 7 x 5, lit up as the counter passes
    v.at(0, 150, -326, z: -20, alpha: clamp((t - 0.4) / 0.4)) {
        text(c, "THIS MONTH \u{00B7} SAMPLE DATA", 0, 0, size: 22, weight: .medium, color: P.nDim, track: 0.1, mono: true)
    }
    for d in 1...31 {
        let idx = d - 1
        let cx = 150.0 + Double(idx % 7) * 94 + 42, cy = -296.0 + Double(idx / 7) * 94 + 42
        if d <= 21 {
            let t0 = TL.tick(d)
            if t < t0 { drawCell(v, cx, cy, d, state: 0, local: 0) ; continue }
            let isCurrent = d == 21 ? true : t < TL.tick(d + 1)
            let sc = 1 + 0.32 * exp(-(t - t0) * 16)
            v.at(0, cx, cy, z: -20, scale: sc) { drawCellBody(c, d, lit: true, current: isCurrent) }
        } else {
            let t0 = 3.125 + Double(d - 22) * 0.06
            drawCell(v, cx, cy, d, state: t < t0 ? 0 : 1, local: clamp((t - t0) / 0.3))
        }
    }
    v.at(0, 150, 205, z: -20, alpha: clamp((t - 3.5) / 0.4)) {
        fill(c, rect(0, -18, 18, 18), P.accent)
        text(c, "logged", 28, -2, size: 22, weight: .medium, color: P.nDim, mono: true)
        hatch(c, rect(150, -18, 18, 18), gap: 6, lw: 1.5, color: P.nDim)
        text(c, "forecast", 178, -2, size: 22, weight: .medium, color: P.nDim, mono: true)
    }
    // the question, word by word on the beat
    let q = 84.0, qy = 392.0
    let w1 = textWidth("Where\u{2019}s your ", size: q, weight: .heavy, track: -0.035)
    let w2 = textWidth("month ", size: q, weight: .heavy, track: -0.035)
    v.at(0, -800, qy, z: -40) {
        kText(c, "Where\u{2019}s your", 0, 0, size: q, weight: .heavy, color: P.white, t: t, t0: TL.words[0])
        kText(c, "month", w1, 0, size: q, weight: .heavy, color: P.white, t: t, t0: TL.words[1])
        kText(c, "going?", w1 + w2, 0, size: q, weight: .heavy, color: P.nGreen, t: t, t0: TL.words[2])
    }
}

private func drawCell(_ v: View, _ cx: Double, _ cy: Double, _ d: Int, state: Int, local: Double) {
    v.at(0, cx, cy, z: -20, alpha: state == 0 ? 1 : 1) {
        if state == 0 { drawCellBody(v.c, d, lit: false, current: false) }
        else {
            let r = rect(-42, -42, 84, 84)
            stroke(v.c, r, withAlpha(P.nLine, local), 1.5)
            hatch(v.c, r.insetBy(dx: 2, dy: 2), gap: 9, lw: 1.5, color: withAlpha(P.nLine, 0.9 * local))
            text(v.c, "\(d)", 0, 8, size: 24, weight: .medium, color: withAlpha(P.nDim, local), align: .center, mono: true)
        }
    }
}
private func drawCellBody(_ c: CGContext, _ d: Int, lit: Bool, current: Bool) {
    let r = rect(-42, -42, 84, 84)
    if lit {
        fill(c, r, current ? P.white : P.accent)
        text(c, "\(d)", 0, 8, size: 26, weight: .semibold, color: current ? P.ink : P.white, align: .center, mono: true)
    } else {
        stroke(c, r, P.nLine, 1.5)
        text(c, "\(d)", 0, 8, size: 24, weight: .medium, color: P.nLine, align: .center, mono: true)
    }
}

// MARK: - Scene 1: Telegram. "Three seconds."

func scene1(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s1 - 1.2 || t > TL.s2 + 0.6 { return }
    let L = t - TL.s1 // local time within the scene

    // headline, three stacked lines
    v.at(1, -760, -300, z: -100, alpha: clamp((L + 0.2) / 0.3)) {
        fill(c, rect(0, -17, 16, 16), P.accent)
        text(c, "FROM TELEGRAM", 32, 0, size: 24, weight: .medium, color: P.muted, track: 0.12, mono: true)
    }
    v.at(1, -760, 0, z: -100) {
        kText(c, "Log it", 0, -170, size: 138, color: P.ink, t: t, t0: TL.s1 - 0.3)
        kText(c, "in three", 0, -30, size: 138, color: P.ink, t: t, t0: TL.s1 - 0.15)
        kText(c, "seconds.", 0, 110, size: 138, color: P.accent, t: t, t0: TL.s1)
        kText(c, "Type the amount and a word.", 0, 205, size: 34, weight: .regular, color: P.text2, track: -0.01, t: t, t0: TL.s1 + 0.9, dur: 0.6)
        kText(c, "It replies with what is safe to spend today.", 0, 250, size: 34, weight: .regular, color: P.text2, track: -0.01, t: t, t0: TL.s1 + 1.1, dur: 0.6)
    }

    // the chat card
    let cardPop = pop(t, at: TL.s1 - 0.12, rise: 80, damping: 12, freq: 14)
    v.at(1, 330, 0 + cardPop.dy, z: 0, scale: lerp(0.86, 1, cardPop.s), alpha: cardPop.a, cull: 600) { drawChat(v) }

    // stopwatch badge: "3 s"
    let sw = pop(t, at: TL.stopwatch, rise: 30)
    v.at(1, 790, -290, z: -170, rot: lerp(-0.2, 0, sw.s), scale: sw.s, alpha: sw.a, cull: 200) {
        circle(c, 9, 9, 85, fill: P.ink)
        circle(c, 0, 0, 85, fill: P.white, stroke: P.ink, lw: 3)
        // sweep one revolution in three seconds, starting when the user starts typing
        let prog = clamp((t - TL.typeStart) / 3.0)
        let a = -Double.pi / 2 + prog * 2 * Double.pi
        c.setStrokeColor(P.accent); c.setLineWidth(16); c.setLineCap(.butt)
        c.addArc(center: .zero, radius: 66, startAngle: CGFloat(-Double.pi / 2), endAngle: CGFloat(a), clockwise: false); c.strokePath()
        text(c, "\(min(3, Int(prog * 3) + 1))s", 0, 17, size: 54, weight: .black, color: P.ink, align: .center, mono: true)
    }

    // payment saved card
    let am = pop(t, at: TL.amountCard, rise: 50)
    v.at(1, -540, 360, z: -150, rot: lerp(0.08, -0.02, am.s), scale: am.s, alpha: am.a, cull: 400) {
        card(c, rect(-210, -85, 420, 170), off: 10)
        text(c, "PAYMENT SAVED", -184, -42, size: 19, weight: .medium, color: P.muted, track: 0.1, mono: true)
        text(c, "\u{2212}\u{20B9}350", -184, 38, size: 70, weight: .heavy, color: P.ink, track: -0.03)
        chip(c, "#food", cx: 130, cy: 24, size: 28)
    }

    // "message deleted" notice
    let dl = pop(t, at: TL.deletedCard, rise: 30)
    v.at(1, 790, 150, z: -120, rot: lerp(-0.1, 0.02, dl.s), scale: dl.s, alpha: dl.a, cull: 300) {
        card(c, rect(-110, -58, 220, 116), fill: P.ink, border: P.ink, shadow: P.accent, off: 9)
        text(c, "MESSAGE", 0, -10, size: 20, weight: .medium, color: P.nDim, track: 0.12, align: .center, mono: true)
        text(c, "deleted", 0, 28, size: 36, weight: .bold, color: P.white, track: -0.02, align: .center)
    }
}

private func drawChat(_ v: View) {
    let c = v.c, t = v.t
    let w = 620.0, h = 800.0, left = -w / 2, top = -h / 2
    card(c, rect(left, top, w, h), fill: P.wash, shadow: P.accent, off: 14)
    // header
    fill(c, rect(left, top, w, 100), P.ink)
    logoMark(c, cx: left + 60, cy: top + 50, s: 56)
    text(c, "LBStash", left + 104, top + 50, size: 30, weight: .semibold, color: P.white, track: -0.02)
    text(c, "bot", left + 104, top + 80, size: 18, weight: .medium, color: P.nDim, mono: true)
    circle(c, left + w - 36, top + 50, 7, fill: P.nGreen)
    // input bar
    let ib = top + h - 90
    fill(c, rect(left, ib, w, 90), P.white)
    line(c, left, ib, left + w, ib, P.ink, 2)
    fill(c, rect(left + w - 76, ib + 16, 58, 58), P.accent)
    let ar = Path2(left + w - 62, ib + 45)
    ar.arrow(c, len: 30)
    // typing in the input bar
    let typed = "/350 food"
    let n = Int(clamp((t - TL.typeStart) / (TL.typeEnd - TL.typeStart)) * Double(typed.count) + 0.0001)
    let typedNow = t < TL.send ? String(typed.prefix(n)) : ""
    if t >= TL.typeStart - 0.15 && t < TL.send {
        let blink = Int(t * 3.2) % 2 == 0
        let tw = text(c, typedNow, left + 26, ib + 57, size: 30, weight: .medium, color: P.ink, mono: true)
        if blink { fill(c, rect(left + 30 + tw, ib + 28, 3, 40), P.accent) }
    } else if t < TL.send {
        text(c, "Message", left + 26, ib + 57, size: 30, weight: .regular, color: P.disabledGrey, mono: false)
    }

    // user bubble 1: "/350 food" (slides up out of the input bar, then is deleted)
    let sendX = clamp((t - TL.send) / 0.38)
    if t >= TL.send {
        let e = easeOutCubic(sendX)
        let y = lerp(ib + 45, top + 190, e)
        var sc = 1.0
        var a = 1.0
        if t >= TL.deleteMsg {
            let u = clamp((t - TL.deleteMsg) / 0.3)
            sc = 1 - easeInCubic(u); a = 1 - u
        }
        if sc > 0.01 {
            c.saveGState(); c.translateBy(x: CGFloat(left + w - 30 - 130), y: CGFloat(y)); c.scaleBy(x: CGFloat(sc), y: CGFloat(sc)); c.setAlpha(CGFloat(a))
            fill(c, rect(-130, -36, 260, 72), P.accent)
            text(c, "/350 food", 0, 11, size: 30, weight: .semibold, color: P.white, align: .center, mono: true)
            c.restoreGState()
        }
    }
    // reply 1
    let dots = t >= TL.dotsStart && t < TL.reply
    if dots {
        fill(c, rect(left + 28, top + 270, 120, 56), P.white); stroke(c, rect(left + 28, top + 270, 120, 56), P.ink, 2)
        for i in 0..<3 {
            let bounce = abs(sin((t - TL.dotsStart) * 9 + Double(i) * 0.9))
            circle(c, left + 58 + Double(i) * 30, top + 298 - bounce * 7, 7, fill: P.ink)
        }
    }
    if t >= TL.reply {
        let p = pop(t, at: TL.reply, rise: 24, damping: 12, freq: 18)
        c.saveGState(); c.translateBy(x: CGFloat(left + 28), y: CGFloat(top + 300 + p.dy)); c.scaleBy(x: CGFloat(lerp(0.7, 1, p.s)), y: CGFloat(lerp(0.7, 1, p.s))); c.setAlpha(CGFloat(p.a))
        fill(c, rect(0, -42, 508, 164), P.white); stroke(c, rect(0, -42, 508, 164), P.ink, 2)
        let w0 = text(c, "Logged ", 22, 14, size: 29, weight: .medium, color: P.ink)
        let w1 = text(c, "\u{20B9}350", 22 + w0, 14, size: 29, weight: .bold, color: P.ink, mono: true)
        let w2 = text(c, " in ", 22 + w0 + w1, 14, size: 29, weight: .medium, color: P.ink)
        chip(c, "#food", cx: 22 + w0 + w1 + w2 + 62, cy: 6, size: 24)
        let cnt = Int(lerp(1230, 880, easeOutCubic(clamp((t - TL.reply) / (TL.countEnd - TL.reply)))))
        let s1 = text(c, "Safe to spend today ", 22, 78, size: 25, weight: .regular, color: P.text2)
        text(c, "\u{20B9}\(inr(cnt))", 22 + s1, 80, size: 36, weight: .black, color: P.accent, mono: true)
        c.restoreGState()
    }
    // user bubble 2: "+1500 salary"
    let m2 = pop(t, at: TL.msg2, rise: 40, damping: 12, freq: 16)
    if m2.a > 0 {
        c.saveGState(); c.translateBy(x: CGFloat(left + w - 30 - 160), y: CGFloat(top + 470 + m2.dy)); c.scaleBy(x: CGFloat(m2.s), y: CGFloat(m2.s)); c.setAlpha(CGFloat(m2.a))
        fill(c, rect(-160, -36, 320, 72), P.accent)
        text(c, "+1500 salary", 0, 11, size: 30, weight: .semibold, color: P.white, align: .center, mono: true)
        c.restoreGState()
    }
    let r2 = pop(t, at: TL.reply2, rise: 24, damping: 12, freq: 18)
    if r2.a > 0 {
        c.saveGState(); c.translateBy(x: CGFloat(left + 28), y: CGFloat(top + 575 + r2.dy)); c.scaleBy(x: CGFloat(lerp(0.7, 1, r2.s)), y: CGFloat(lerp(0.7, 1, r2.s))); c.setAlpha(CGFloat(r2.a))
        fill(c, rect(0, -34, 470, 100), P.white); stroke(c, rect(0, -34, 470, 100), P.ink, 2)
        let a0 = text(c, "Logged ", 22, 6, size: 29, weight: .medium, color: P.ink)
        let a1 = text(c, "+\u{20B9}1,500", 22 + a0, 6, size: 29, weight: .bold, color: P.accent, mono: true)
        text(c, " in", 22 + a0 + a1, 6, size: 29, weight: .medium, color: P.ink)
        chip(c, "#salary", cx: 118, cy: 44, size: 22)
        c.restoreGState()
    }
}

extension P { static let disabledGrey = C(0xB1B1BA) }

/// Tiny helper to draw the send arrow without a path library.
struct Path2 {
    let x: Double, y: Double
    init(_ x: Double, _ y: Double) { self.x = x; self.y = y }
    func arrow(_ c: CGContext, len: Double) {
        c.setStrokeColor(P.white); c.setLineWidth(4); c.setLineCap(.butt); c.setLineJoin(.miter)
        c.move(to: CGPoint(x: x - len / 2, y: y)); c.addLine(to: CGPoint(x: x + len / 2, y: y))
        c.move(to: CGPoint(x: x + 2, y: y - len / 2 + 2)); c.addLine(to: CGPoint(x: x + len / 2, y: y)); c.addLine(to: CGPoint(x: x + 2, y: y + len / 2 - 2))
        c.strokePath()
    }
}

// MARK: - Scene 2: salary lands, rent leaves, an unknown payee

func scene2(_ v: View) {
    let c = v.c, t = v.t
    if t < TL.s2 - 1.2 || t > TL.s3 + 0.6 { return }
    let L = t - TL.s2

    // headline (white on green)
    v.at(2, -900, -360, z: -110, alpha: clamp((L + 0.25) / 0.3)) {
        fill(c, rect(0, -17, 16, 16), P.white)
        text(c, "A MONTH, AUTOMATIC", 32, 0, size: 24, weight: .medium, color: withAlpha(P.white, 0.8), track: 0.12, mono: true)
    }
    v.at(2, -900, 0, z: -110) {
        kText(c, "Salary lands.", 0, -225, size: 132, color: P.white, t: t, t0: TL.s2 - 0.3)
        kText(c, "Rent leaves.", 0, -90, size: 132, color: P.ink, t: t, t0: TL.s2 - 0.1)
    }

    // SMS card
    let sms = pop(t, at: TL.smsPop, rise: 60, damping: 12, freq: 14)
    v.at(2, -560, 130, z: 0, rot: lerp(-0.05, 0, sms.s), scale: sms.s, alpha: sms.a, cull: 500) {
        card(c, rect(-280, -160, 560, 320), off: 12)
        text(c, "BANK MESSAGE", -250, -112, size: 20, weight: .medium, color: P.muted, track: 0.1, mono: true)
        let full = ["HDFCBK: Rs 85,000.00", "credited to a/c XX4321", "by ACME TECHNOLOGIES."]
        let total = full.reduce(0) { $0 + $1.count }
        var left = Int(clamp((t - TL.smsType0) / (TL.smsType1 - TL.smsType0)) * Double(total))
        for (i, ln) in full.enumerated() {
            let take = min(ln.count, max(0, left)); left -= ln.count
            let s = String(ln.prefix(take))
            text(c, s, -250, -52 + Double(i) * 48, size: 31, weight: .medium, color: P.ink, mono: true)
        }
        // highlight the amount
        if t > TL.smsType1 {
            let u = clamp((t - TL.smsType1) / 0.25)
            let hw = textWidth("85,000.00", size: 31, weight: .medium, mono: true)
            let hx = -250 + textWidth("HDFCBK: Rs ", size: 31, weight: .medium, mono: true)
            c.setFillColor(withAlpha(P.accent, 0.28 * u)); c.fill(rect(hx - 4, -80, hw * u + 8, 38))
        }
    }
    // arrow
    if t > TL.arrow {
        let u = easeOutCubic(clamp((t - TL.arrow) / 0.2))
        v.at(2, -250, 130, z: -30, cull: 300) {
            c.setStrokeColor(P.ink); c.setLineWidth(6)
            c.move(to: .zero); c.addLine(to: CGPoint(x: 90 * u, y: 0)); c.strokePath()
            if u > 0.8 {
                c.setFillColor(P.ink); c.move(to: CGPoint(x: 112, y: 0)); c.addLine(to: CGPoint(x: 84, y: -22)); c.addLine(to: CGPoint(x: 84, y: 22)); c.closePath(); c.fillPath()
            }
        }
    }
    // salary card: flips in, coins burst
    if t >= TL.salary - 0.01 {
        let x = t - TL.salary
        let flip = clamp(spring(x, damping: 9, freq: 12), 0, 1.2)
        let sc = lerp(0.6, 1, min(1, flip))
        v.at(2, 80, 130, z: -10, scale: sc, alpha: clamp(x / 0.05), cull: 500) {
            c.scaleBy(x: CGFloat(max(0.02, min(1.04, flip))), y: 1)
            card(c, rect(-240, -160, 480, 320), shadow: P.ink, off: 12)
            text(c, "INCOME", -210, -112, size: 20, weight: .medium, color: P.muted, track: 0.1, mono: true)
            text(c, "+85,000", -210, 38, size: 110, weight: .black, color: P.accent, track: -0.04)
            chip(c, "#salary", cx: -130, cy: 106, size: 28)
            text(c, "no typing", 150, 112, size: 22, weight: .medium, color: P.muted, align: .center, mono: true)
        }
        // coins
        for i in 0..<14 {
            let ang = -Double.pi / 2 + (hash01(i * 7 + 1) - 0.5) * 2.4
            let sp = 380 + hash01(i * 13 + 5) * 420
            let tt = x
            if tt > 1.0 { continue }
            let px = 80 + cos(ang) * sp * tt, py = 130 + sin(ang) * sp * tt + 900 * tt * tt
            v.at(2, px, py, z: -80, alpha: 1 - clamp((tt - 0.6) / 0.4), cull: 80) {
                circle(c, 0, 0, 17, fill: P.white, stroke: P.ink, lw: 3)
                text(c, "\u{20B9}", 0, 9, size: 22, weight: .heavy, color: P.ink, align: .center)
            }
        }
    }

    // rent / repeats card with growing stems
    let rp = pop(t, at: TL.rentPop, rise: 60, damping: 12, freq: 14)
    v.at(2, 790, 150, z: 0, rot: lerp(0.05, 0, rp.s), scale: rp.s, alpha: rp.a, cull: 600) {
        card(c, rect(-300, -190, 600, 380), off: 12)
        text(c, "REPEATS \u{00B7} EVERY MONTH", -270, -142, size: 20, weight: .medium, color: P.muted, track: 0.1, mono: true)
        let x0 = -260.0, x1 = 260.0, base = 120.0
        line(c, x0, base, x1, base, P.ink, 2)
        for d in 1...30 where d % 5 == 0 || d == 1 {
            let x = x0 + Double(d - 1) / 30 * (x1 - x0)
            line(c, x, base, x, base + 8, P.ink, 2)
            text(c, "\(d)", x, base + 32, size: 16, weight: .medium, color: P.muted, align: .center, mono: true)
        }
        func stem(_ day: Int, _ hgt: Double, _ t0: Double, _ label: String, _ lx: Double, _ la: Align) {
            let x = x0 + Double(day - 1) / 30 * (x1 - x0)
            let g = clamp((t - t0) / 0.5)
            let e = 1 + 1.70158 * pow(g - 1, 3) + 0.70158 * pow(g - 1, 2) // easeOutBack
            let hh = hgt * (g <= 0 ? 0 : e)
            fill(c, rect(x - 8, base - hh, 16, hh), P.accent)
            if g > 0.4 { text(c, label, lx, base - hgt - 16, size: 24, weight: .semibold, color: P.ink, align: la, mono: true) }
        }
        stem(5, 210, TL.stem1, "Rent \u{2212}24,000", x0 + 0, .left)
        stem(28, 70, TL.stem2, "SIP \u{2212}15,000", x1 + 20, .right)
    }

    // the unknown payee
    let up = pop(t, at: TL.upiPop, rise: 60, damping: 12, freq: 14)
    v.at(2, 300, 610, z: 0, rot: lerp(-0.04, 0, up.s), scale: up.s, alpha: up.a, cull: 600) {
        card(c, rect(-360, -130, 720, 260), off: 12)
        text(c, "UPI \u{00B7} RAMESH K", -330, -50, size: 40, weight: .semibold, color: P.ink, track: -0.01)
        text(c, "\u{2212}1,200", 330, -50, size: 40, weight: .semibold, color: P.ink, align: .right, mono: true)
        line(c, -330, -22, 330, -22, P.rule, 2)
        // "needs a tag" pulses amber until the chip stamps in
        let stamped = t >= TL.tagStamp
        if !stamped {
            let pulse = 0.5 + 0.5 * sin((t - TL.upiPop) * 9)
            fill(c, rect(-330, 14, 232, 52), mix(P.warn, C(0xFFD966), pulse))
            text(c, "needs a tag", -214, 50, size: 28, weight: .semibold, color: P.ink, align: .center, mono: true)
        } else {
            let x = t - TL.tagStamp
            let sc = 1 + 1.4 * exp(-x * 20) // stamps down from large
            c.saveGState(); c.translateBy(x: -214, y: 40); c.scaleBy(x: CGFloat(sc), y: CGFloat(sc)); c.rotate(by: CGFloat(-0.12 * exp(-x * 12)))
            chip(c, "#other", cx: 0, cy: 0, size: 30)
            c.restoreGState()
            let rm = clamp((t - TL.remembered) / 0.3)
            text(c, "\u{2713} remembered", -60, 50, size: 28, weight: .semibold, color: withAlpha(P.accent, rm), mono: true)
        }
        text(c, "Next time, it just tags itself.", -330, 108, size: 24, weight: .regular, color: P.muted, mono: false)
    }
    v.at(2, -420, 392, z: -60) {
        kText(c, "Tag it", 0, 0, size: 96, color: P.white, t: t, t0: TL.upiPop + 0.1)
        kText(c, "once.", textWidth("Tag it ", size: 96, weight: .black, track: -0.035), 0, size: 96, color: P.ink, t: t, t0: TL.upiPop + 0.25)
    }
}

func mix(_ a: CGColor, _ b: CGColor, _ u: Double) -> CGColor {
    let ca = a.components ?? [0, 0, 0, 1], cb = b.components ?? [0, 0, 0, 1]
    return CGColor(srgbRed: lerp(Double(ca[0]), Double(cb[0]), u), green: lerp(Double(ca[1]), Double(cb[1]), u), blue: lerp(Double(ca[2]), Double(cb[2]), u), alpha: 1)
}
