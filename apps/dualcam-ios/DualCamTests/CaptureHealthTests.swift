import XCTest

final class CaptureHealthTests: XCTestCase {
    func testStartupAllowsWarmupButReportsMissingMicrophone() {
        var health = CaptureHealth(startedAt: 100)
        health.received(.front, mediaTime: 1, at: 105.9)
        health.received(.rear, mediaTime: 1, at: 105.9)
        XCTAssertTrue(health.stalled(at: 105.9).isEmpty)
        XCTAssertEqual(health.stalled(at: 106), [.audio])
    }

    func testFrozenRearCameraIsDetectedWhileOtherStreamsKeepFlowing() {
        var health = CaptureHealth(startedAt: 100)
        for stream in CaptureHealth.Stream.allCases { health.received(stream, mediaTime: 1, at: 100.1) }
        health.received(.front, mediaTime: 6, at: 105)
        health.received(.audio, mediaTime: 6, at: 105)
        XCTAssertEqual(health.stalled(at: 105), [.rear])
        health.received(.rear, mediaTime: 6.1, at: 105.1)
        XCTAssertTrue(health.stalled(at: 105.1).isEmpty)
    }

    func testRepeatedOrInvalidTimestampsCannotKeepADeadStreamHealthy() {
        var health = CaptureHealth(startedAt: 100)
        for stream in CaptureHealth.Stream.allCases { health.received(stream, mediaTime: 1, at: 100.1) }
        health.received(.front, mediaTime: 5, at: 104.5)
        health.received(.rear, mediaTime: 5, at: 104.5)
        health.received(.audio, mediaTime: 1, at: 104.5)
        health.received(.audio, mediaTime: .nan, at: 104.5)
        XCTAssertEqual(health.stalled(at: 104.5), [.audio])
    }
}
