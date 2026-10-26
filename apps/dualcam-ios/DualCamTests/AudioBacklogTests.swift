import XCTest

final class AudioBacklogTests: XCTestCase {
    func testTemporaryEncoderBackpressurePreservesEverySampleInOrder() throws {
        var backlog = AudioBacklog<Int>(limit: 8)
        var written: [Int] = []
        for value in 1...5 { try backlog.enqueue(value) }
        try backlog.drain(ready: { false }, write: { written.append($0) })
        XCTAssertTrue(written.isEmpty)
        XCTAssertEqual(backlog.count, 5)
        try backlog.drain(ready: { written.count < 2 }, write: { written.append($0) })
        try backlog.enqueue(6)
        try backlog.drain(ready: { true }, write: { written.append($0) })
        XCTAssertEqual(written, [1, 2, 3, 4, 5, 6])
        XCTAssertTrue(backlog.isEmpty)
    }

    func testOverflowReportsFailureWithoutReplacingBufferedAudio() throws {
        var backlog = AudioBacklog<Int>(limit: 2)
        try backlog.enqueue(10)
        try backlog.enqueue(20)
        XCTAssertThrowsError(try backlog.enqueue(30))
        var written: [Int] = []
        try backlog.drain(ready: { true }, write: { written.append($0) })
        XCTAssertEqual(written, [10, 20])
    }

    func testFailedAppendDoesNotConsumeTheUnwrittenSample() throws {
        var backlog = AudioBacklog<Int>(limit: 2)
        try backlog.enqueue(10)
        XCTAssertThrowsError(try backlog.drain(ready: { true }, write: { _ in
            throw RecorderError.message("Injected disk error")
        }))
        var written: [Int] = []
        try backlog.drain(ready: { true }, write: { written.append($0) })
        XCTAssertEqual(written, [10])
    }
}
