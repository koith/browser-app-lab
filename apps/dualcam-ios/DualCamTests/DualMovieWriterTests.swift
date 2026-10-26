import AVFoundation
import XCTest

final class DualMovieWriterTests: XCTestCase {
    func testBothMoviesContainReadableVideoAndAudio() async throws {
        let folder = try makeFolder()
        defer { try? FileManager.default.removeItem(at: folder) }
        let writer = DualMovieWriter(folder: folder)
        let queue = DispatchQueue(label: "test.movie-writer")
        let duration: TimeInterval = try await withCheckedThrowingContinuation { continuation in
            queue.async {
                do {
                    // Deliberately offset the first camera frames to exercise clock alignment.
                    try writer.appendVideo(self.makeVideo(frame: 0), side: .front)
                    try writer.appendVideo(self.makeVideo(frame: 1), side: .rear)
                    try writer.appendAudio(self.makeAudio(frame: 0))
                    for frame in 1...60 {
                        try writer.appendVideo(self.makeVideo(frame: frame), side: .front)
                        try writer.appendVideo(self.makeVideo(frame: frame), side: .rear)
                        try writer.appendAudio(self.makeAudio(frame: frame))
                        Thread.sleep(forTimeInterval: 0.005)
                    }
                    writer.finish(on: queue) { continuation.resume(with: $0) }
                } catch { continuation.resume(throwing: error) }
            }
        }
        XCTAssertGreaterThan(duration, 1.8)
        for name in ["front.mov", "rear.mov"] {
            let asset = AVURLAsset(url: folder.appendingPathComponent(name))
            let video = try await asset.loadTracks(withMediaType: .video)
            let audio = try await asset.loadTracks(withMediaType: .audio)
            XCTAssertEqual(video.count, 1)
            XCTAssertEqual(audio.count, 1, "\(name) must preserve microphone audio")
            let movieDuration = try await asset.load(.duration)
            XCTAssertGreaterThan(CMTimeGetSeconds(movieDuration), 1.5)
            let track = try XCTUnwrap(audio.first)
            let reader = try AVAssetReader(asset: asset)
            let output = AVAssetReaderTrackOutput(track: track, outputSettings: [AVFormatIDKey: kAudioFormatLinearPCM])
            reader.add(output)
            XCTAssertTrue(reader.startReading())
            var decodedSamples = 0
            while let sample = output.copyNextSampleBuffer() {
                decodedSamples += CMSampleBufferGetNumSamples(sample)
            }
            XCTAssertEqual(reader.status, .completed)
            XCTAssertGreaterThanOrEqual(decodedSamples, 86_400,
                                        "Both movies must retain at least 1.8 seconds of the 2-second microphone input")
            reader.cancelReading()
        }
    }

    func testStoppingBeforeSecondCameraDoesNotReportSuccess() throws {
        let folder = try makeFolder()
        defer { try? FileManager.default.removeItem(at: folder) }
        let writer = DualMovieWriter(folder: folder)
        try writer.appendVideo(makeVideo(frame: 0), side: .front)
        try writer.appendAudio(makeAudio(frame: 0))
        var failed = false
        writer.finish(on: .main) { result in
            if case .failure = result { failed = true }
        }
        XCTAssertTrue(failed)
        XCTAssertFalse(FileManager.default.fileExists(atPath: folder.appendingPathComponent("front.mov").path))
    }

    private func makeFolder() throws -> URL {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        return folder
    }

    private func timestamp(_ frame: Int) -> CMTime {
        CMTime(value: Int64(3_000 + frame), timescale: 30)
    }

    private func makeVideo(frame: Int) throws -> CMSampleBuffer {
        var image: CVPixelBuffer?
        XCTAssertEqual(CVPixelBufferCreate(kCFAllocatorDefault, 64, 64, kCVPixelFormatType_32BGRA, nil, &image), kCVReturnSuccess)
        let buffer = try XCTUnwrap(image)
        CVPixelBufferLockBaseAddress(buffer, [])
        if let address = CVPixelBufferGetBaseAddress(buffer) {
            memset(address, Int32(frame % 255), CVPixelBufferGetDataSize(buffer))
        }
        CVPixelBufferUnlockBaseAddress(buffer, [])
        var format: CMVideoFormatDescription?
        XCTAssertEqual(CMVideoFormatDescriptionCreateForImageBuffer(
            allocator: kCFAllocatorDefault, imageBuffer: buffer, formatDescriptionOut: &format), noErr)
        var timing = CMSampleTimingInfo(duration: CMTime(value: 1, timescale: 30),
                                        presentationTimeStamp: timestamp(frame), decodeTimeStamp: .invalid)
        var sample: CMSampleBuffer?
        XCTAssertEqual(CMSampleBufferCreateReadyWithImageBuffer(
            allocator: kCFAllocatorDefault, imageBuffer: buffer, formatDescription: try XCTUnwrap(format),
            sampleTiming: &timing, sampleBufferOut: &sample), noErr)
        return try XCTUnwrap(sample)
    }

    private func makeAudio(frame: Int) throws -> CMSampleBuffer {
        let sampleCount = 1_600
        var description = AudioStreamBasicDescription(
            mSampleRate: 48_000, mFormatID: kAudioFormatLinearPCM,
            mFormatFlags: kAudioFormatFlagIsSignedInteger | kAudioFormatFlagIsPacked,
            mBytesPerPacket: 2, mFramesPerPacket: 1, mBytesPerFrame: 2,
            mChannelsPerFrame: 1, mBitsPerChannel: 16, mReserved: 0)
        var format: CMAudioFormatDescription?
        XCTAssertEqual(CMAudioFormatDescriptionCreate(
            allocator: kCFAllocatorDefault, asbd: &description, layoutSize: 0, layout: nil,
            magicCookieSize: 0, magicCookie: nil, extensions: nil, formatDescriptionOut: &format), noErr)
        var block: CMBlockBuffer?
        XCTAssertEqual(CMBlockBufferCreateWithMemoryBlock(
            allocator: kCFAllocatorDefault, memoryBlock: nil, blockLength: sampleCount * 2,
            blockAllocator: kCFAllocatorDefault, customBlockSource: nil,
            offsetToData: 0, dataLength: sampleCount * 2, flags: 0, blockBufferOut: &block), noErr)
        let data = try XCTUnwrap(block)
        XCTAssertEqual(CMBlockBufferFillDataBytes(with: 0, blockBuffer: data,
                                                 offsetIntoDestination: 0, dataLength: sampleCount * 2), noErr)
        var timing = CMSampleTimingInfo(duration: CMTime(value: 1, timescale: 48_000),
                                        presentationTimeStamp: timestamp(frame), decodeTimeStamp: .invalid)
        var sampleSize = 2
        var sample: CMSampleBuffer?
        XCTAssertEqual(CMSampleBufferCreateReady(
            allocator: kCFAllocatorDefault, dataBuffer: data, formatDescription: try XCTUnwrap(format),
            sampleCount: sampleCount, sampleTimingEntryCount: 1, sampleTimingArray: &timing,
            sampleSizeEntryCount: 1, sampleSizeArray: &sampleSize, sampleBufferOut: &sample), noErr)
        return try XCTUnwrap(sample)
    }
}
