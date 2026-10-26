import CoreMedia

/// Both movies use one clock origin. No buffer before that origin is written.
struct RecordingTimeline {
    private(set) var origin: CMTime?
    private var latest: [CameraSide: CMTime] = [:]

    mutating func start(front: CMTime, rear: CMTime) {
        guard origin == nil, front.isNumeric, rear.isNumeric else { return }
        origin = CMTimeCompare(front, rear) >= 0 ? front : rear
    }

    mutating func accepts(_ time: CMTime, for side: CameraSide) -> Bool {
        guard time.isNumeric, let origin, CMTimeCompare(time, origin) >= 0 else { return false }
        if let previous = latest[side], CMTimeCompare(time, previous) <= 0 { return false }
        latest[side] = time
        return true
    }
}

enum CameraSide: Hashable {
    case front, rear
}
