import Foundation

/// Uses monotonic uptime, so changing the phone's clock cannot hide a stalled stream.
struct CaptureHealth {
    enum Stream: String, CaseIterable {
        case front = "전면 카메라"
        case rear = "후면 카메라"
        case audio = "마이크"
    }

    let startedAt: TimeInterval
    private var arrivals: [Stream: TimeInterval] = [:]
    private var timestamps: [Stream: TimeInterval] = [:]

    init(startedAt: TimeInterval) { self.startedAt = startedAt }

    mutating func received(_ stream: Stream, mediaTime: TimeInterval, at uptime: TimeInterval) {
        guard mediaTime.isFinite, uptime.isFinite else { return }
        if let previous = timestamps[stream], mediaTime <= previous { return }
        timestamps[stream] = mediaTime
        arrivals[stream] = uptime
    }

    func stalled(at uptime: TimeInterval) -> [Stream] {
        if arrivals.count < Stream.allCases.count {
            guard uptime - startedAt >= 6 else { return [] }
            return Stream.allCases.filter { arrivals[$0] == nil || uptime - arrivals[$0]! >= 4 }
        }
        return Stream.allCases.filter { uptime - arrivals[$0]! >= 4 }
    }
}
