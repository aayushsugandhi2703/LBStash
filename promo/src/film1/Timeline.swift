import Foundation
import CoreGraphics

// MARK: - Camera path (all moves land on bars/beats)

let cameraKeys: [Key] = [
    // Scene 0: punch-in on the slam, then a slow push; whip right on the last beat
    key(0.0, stage: 0, -60, 0, zoom: 1.35, roll: 1.5),
    key(0.9, stage: 0, -60, 0, zoom: 1.0, roll: 0, ease: easeOutCubic),
    key(4.3, stage: 0, 10, 10, zoom: 1.06, roll: -1.0),
    // whip 0 -> 1, lands on the drop at 5.0
    key(5.0, stage: 1, 90, 0, zoom: 1.0, roll: -1.0, bz: -0.35, br: 5),

    // Scene 1: telegram. wide, push onto the reply, then out to see the notices
    key(6.3, stage: 1, 60, 0, zoom: 1.02, roll: 0.5),
    key(7.0, stage: 1, 330, -70, zoom: 1.45, roll: 1.5),
    key(8.4, stage: 1, 340, -60, zoom: 1.52, roll: 1.2),
    key(9.1, stage: 1, 330, 60, zoom: 1.0, roll: -1.0),
    key(9.3, stage: 1, 330, 60, zoom: 1.0, roll: -1.0),
    // whip 1 -> 2
    key(10.0, stage: 2, -250, 70, zoom: 1.0, roll: 1.0, bz: -0.3, br: -5),

    // Scene 2: sms + salary, pan to rent, drop to the unknown payee
    key(11.5, stage: 2, -230, 90, zoom: 1.06, roll: -1.5),
    key(12.4, stage: 2, 520, 150, zoom: 1.1, roll: 1.5),
    key(12.9, stage: 2, 540, 170, zoom: 1.12, roll: 1.2),
    key(13.9, stage: 2, 280, 520, zoom: 1.2, roll: -1.5),
    key(14.3, stage: 2, 280, 520, zoom: 1.2, roll: -1.5),
    // whip 2 -> 3 (down)
    key(15.0, stage: 3, -250, 60, zoom: 0.95, roll: 0, bz: -0.3, br: 6),

    // Scene 3: limit card, orbit to the tally, then dolly into the -850 and cut
    key(16.1, stage: 3, -290, 105, zoom: 1.12, roll: -2.0),
    key(17.3, stage: 3, -150, 80, zoom: 1.0, roll: 1.0),
    key(18.0, stage: 3, 380, 120, zoom: 1.12, roll: 2.0),
    key(18.9, stage: 3, 450, 150, zoom: 1.1, roll: -1.0),
    key(19.99, stage: 3, 700, 230, zoom: 5.5, roll: 0, ease: easeInQuart),

    // Scene 4: hard cut, pull back from the "21", ride the line into the crash, swing out, crane down to the numbers
    key(20.0, stage: 4, -560, -250, zoom: 1.7, roll: -3.0),
    key(21.2, stage: 4, 0, 30, zoom: 1.0, roll: 0, ease: easeOutCubic),
    key(22.3, stage: 4, 120, 70, zoom: 1.05, roll: 1.0),
    key(24.3, stage: 4, 560, 120, zoom: 1.8, roll: -2.0, ease: easeInCubic),
    key(24.8, stage: 4, 580, 120, zoom: 1.85, roll: -2.0),
    key(25.5, stage: 4, 0, 40, zoom: 0.95, roll: 2.0, ease: easeOutCubic, br: -9),
    key(26.4, stage: 4, 60, 60, zoom: 1.04, roll: -1.0),
    key(27.0, stage: 4, 0, 170, zoom: 0.92, roll: 0),
    key(29.3, stage: 4, 0, 180, zoom: 0.92, roll: 0.5),
    // whip 4 -> 5
    key(30.0, stage: 5, 20, 0, zoom: 1.0, roll: 0, bz: -0.3, br: -5),

    // Scene 5: rows get redacted one by one, big stamp, then the five locks
    key(31.4, stage: 5, 330, -60, zoom: 1.28, roll: -1.5),
    key(33.2, stage: 5, 350, 100, zoom: 1.28, roll: 1.5),
    key(33.7, stage: 5, 100, 20, zoom: 0.92, roll: 0),
    key(34.6, stage: 5, 20, 0, zoom: 1.0, roll: 0),
    key(36.6, stage: 5, 20, 10, zoom: 1.0, roll: 1.2),
    key(36.8, stage: 5, 20, 10, zoom: 1.0, roll: 1.2),
    // whip 5 -> 6 (up)
    key(37.5, stage: 6, 0, 20, zoom: 1.0, roll: -2.0, bz: -0.3, br: 6),

    // Scene 6: services grid, slow orbit
    key(39.0, stage: 6, 0, 30, zoom: 1.06, roll: 2.0),
    key(39.4, stage: 6, 0, 30, zoom: 1.06, roll: 2.0),
    // whip 6 -> 7, lands on the final hit
    key(40.0, stage: 7, 0, 0, zoom: 1.2, roll: 0, bz: -0.35, br: -5),
    key(41.6, stage: 7, 0, 10, zoom: 1.0, roll: 0, ease: easeOutCubic),
    key(46.5, stage: 7, 0, 10, zoom: 1.04, roll: 0, ease: easeLinear),
]

func cameraAt(_ t: Double) -> Cam {
    var cam = sampleKeys(cameraKeys, t)
    // handheld float, always on
    cam.x += 7 * sin(t * 0.83) + 4 * sin(t * 1.9 + 1)
    cam.y += 6 * sin(t * 0.67 + 2) + 3 * sin(t * 2.3)
    cam.roll += 0.0022 * sin(t * 0.5 + 1)
    // impact shakes
    for (ti, amp) in impacts where t >= ti && t < ti + 0.9 {
        let d = t - ti, f = exp(-d * 7)
        cam.x += amp * f * sin(d * 63)
        cam.y += amp * f * cos(d * 71)
        cam.roll += amp * 0.0002 * f * sin(d * 45)
    }
    return cam
}

/// Moments that kick the camera and flash the frame: (time, strength).
let impacts: [(Double, Double)] = [(0.0, 26), (2.5, 22), (5.0, 24), (10.0, 20), (15.0, 18), (20.0, 34), (24.4, 36), (25.0, 20), (30.0, 28), (33.75, 30), (40.0, 40)]

/// Frames that are mid-whip need many motion-blur samples.
let whipWindows: [(Double, Double)] = [(4.3, 5.0), (9.3, 10.0), (14.3, 15.0), (19.5, 20.0), (29.3, 30.0), (36.8, 37.5), (39.4, 40.0)]
