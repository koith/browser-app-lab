import CoreMedia
import XCTest

final class RecordingTimelineTests: XCTestCase {
    private func time(_ seconds: Double) -> CMTime { CMTime(seconds: seconds, preferredTimescale: 60_000) }

    func testCamerasShareLaterFirstFrameAsOrigin() {
        var timeline = RecordingTimeline()
        timeline.start(front: time(12), rear: time(12.1))
        XCTAssertEqual(CMTimeGetSeconds(timeline.origin!), 12.1, accuracy: 0.0001)
        XCTAssertFalse(timeline.accepts(time(12), for: .front))
        XCTAssertTrue(timeline.accepts(time(12.1), for: .rear))
        XCTAssertTrue(timeline.accepts(time(12.11), for: .front))
    }

    func testCameraClocksDoNotRejectEachOthersFrames() {
        var timeline = RecordingTimeline()
        timeline.start(front: time(5), rear: time(5))
        XCTAssertTrue(timeline.accepts(time(6), for: .front))
        XCTAssertTrue(timeline.accepts(time(5.5), for: .rear))
        XCTAssertFalse(timeline.accepts(time(6), for: .front))
        XCTAssertFalse(timeline.accepts(time(5.9), for: .front))
        XCTAssertTrue(timeline.accepts(time(6.1), for: .front))
    }

    func testInvalidTimestampsAndRepeatedStartsCannotMoveOrigin() {
        var timeline = RecordingTimeline()
        timeline.start(front: .invalid, rear: time(2))
        XCTAssertNil(timeline.origin)
        XCTAssertFalse(timeline.accepts(time(3), for: .rear))
        timeline.start(front: time(2), rear: time(2))
        timeline.start(front: time(100), rear: time(100))
        XCTAssertEqual(CMTimeGetSeconds(timeline.origin!), 2)
        XCTAssertFalse(timeline.accepts(.indefinite, for: .front))
    }
}
