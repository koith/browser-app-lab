import AVFoundation

/// All methods except AVAssetWriter's finish callbacks run on the capture queue.
/// Data outputs + AVAssetWriter add no app-generated recording start/stop sounds.
final class DualMovieWriter {
    private let folder: URL
    private var frontSample: CMSampleBuffer?
    private var rearSample: CMSampleBuffer?
    private var audioSamples: [CMSampleBuffer] = []
    private var front: MovieSink?
    private var rear: MovieSink?
    private var timeline = RecordingTimeline()
    private var finishing = false
    private(set) var duration: TimeInterval = 0
    private(set) var droppedVideoFrames = 0

    init(folder: URL) { self.folder = folder }

    func appendVideo(_ sample: CMSampleBuffer, side: CameraSide) throws {
        guard !finishing, CMSampleBufferDataIsReady(sample) else { return }
        if front == nil {
            if side == .front { frontSample = sample } else { rearSample = sample }
            try startIfReady()
            return
        }
        try writeVideo(sample, side: side)
    }

    func appendAudio(_ sample: CMSampleBuffer) throws {
        guard !finishing, CMSampleBufferDataIsReady(sample) else { return }
        if front == nil {
            // Bound memory if a camera fails to deliver frames. The engine also times out.
            audioSamples.append(sample)
            if audioSamples.count > 90 { audioSamples.removeFirst() }
            try startIfReady()
            return
        }
        try writeAudio(sample)
    }

    private func startIfReady() throws {
        guard let frontSample, let rearSample, let audioSample = audioSamples.first,
              let audioFormat = CMSampleBufferGetFormatDescription(audioSample) else { return }
        timeline.start(front: CMSampleBufferGetPresentationTimeStamp(frontSample),
                       rear: CMSampleBufferGetPresentationTimeStamp(rearSample))
        guard let origin = timeline.origin else {
            throw RecorderError.message("카메라 시간 정보를 읽지 못했습니다.")
        }
        do {
            let frontSink = try MovieSink(url: folder.appendingPathComponent("front.mov"),
                                          videoSample: frontSample, audioFormat: audioFormat)
            front = frontSink
            let rearSink = try MovieSink(url: folder.appendingPathComponent("rear.mov"),
                                         videoSample: rearSample, audioFormat: audioFormat)
            rear = rearSink
            try frontSink.start(at: origin)
            try rearSink.start(at: origin)
            try writeVideo(frontSample, side: .front)
            try writeVideo(rearSample, side: .rear)
            for sample in audioSamples { try writeAudio(sample) }
            self.frontSample = nil
            self.rearSample = nil
            audioSamples.removeAll()
        } catch {
            front?.cancel()
            rear?.cancel()
            throw error
        }
    }

    private func writeVideo(_ sample: CMSampleBuffer, side: CameraSide) throws {
        let time = CMSampleBufferGetPresentationTimeStamp(sample)
        guard timeline.accepts(time, for: side), let origin = timeline.origin else { return }
        let sink = side == .front ? front : rear
        if try sink?.appendVideo(sample) == false { droppedVideoFrames += 1 }
        duration = max(duration, CMTimeGetSeconds(CMTimeSubtract(time, origin)))
    }

    private func writeAudio(_ sample: CMSampleBuffer) throws {
        guard let origin = timeline.origin,
              CMTimeCompare(CMSampleBufferGetPresentationTimeStamp(sample), origin) >= 0 else { return }
        try front?.appendAudio(sample)
        try rear?.appendAudio(sample)
    }

    func finish(on queue: DispatchQueue, completion: @escaping (Result<TimeInterval, Error>) -> Void) {
        guard !finishing else { return }
        finishing = true
        guard let front, let rear else {
            completion(.failure(RecorderError.message("카메라·마이크 데이터가 준비되기 전에 녹화가 종료됐습니다.")))
            return
        }
        let group = DispatchGroup()
        for sink in [front, rear] {
            group.enter()
            sink.finish { group.leave() }
        }
        group.notify(queue: queue) {
            if let error = front.failure ?? rear.failure { completion(.failure(error)) }
            else { completion(.success(self.duration)) }
        }
    }
}

private final class MovieSink {
    private let writer: AVAssetWriter
    private let video: AVAssetWriterInput
    private let audio: AVAssetWriterInput
    private var videoCount = 0
    private var audioCount = 0

    var failure: Error? {
        if let error = writer.error { return error }
        guard writer.status == .completed, videoCount > 0, audioCount > 0 else {
            return RecorderError.message("영상 또는 음성을 완전히 저장하지 못했습니다. 파일 앱의 DualCam 폴더를 확인해 주세요.")
        }
        return nil
    }

    init(url: URL, videoSample: CMSampleBuffer, audioFormat: CMFormatDescription) throws {
        guard let image = CMSampleBufferGetImageBuffer(videoSample) else {
            throw RecorderError.message("카메라 영상 형식을 읽지 못했습니다.")
        }
        writer = try AVAssetWriter(outputURL: url, fileType: .mov)
        video = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: CVPixelBufferGetWidth(image),
            AVVideoHeightKey: CVPixelBufferGetHeight(image),
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 3_000_000,
                AVVideoExpectedSourceFrameRateKey: 30,
                AVVideoMaxKeyFrameIntervalKey: 30
            ]
        ])
        let channelCount = Int(CMAudioFormatDescriptionGetStreamBasicDescription(audioFormat)?.pointee.mChannelsPerFrame ?? 1)
        let sampleRate = CMAudioFormatDescriptionGetStreamBasicDescription(audioFormat)?.pointee.mSampleRate ?? 48_000
        audio = AVAssetWriterInput(mediaType: .audio, outputSettings: [
            AVFormatIDKey: kAudioFormatMPEG4AAC,
            AVSampleRateKey: sampleRate,
            AVNumberOfChannelsKey: channelCount,
            AVEncoderBitRateKey: 128_000
        ], sourceFormatHint: audioFormat)
        video.expectsMediaDataInRealTime = true
        audio.expectsMediaDataInRealTime = true
        guard writer.canAdd(video), writer.canAdd(audio) else {
            throw RecorderError.message("이 기기에서 영상·음성 인코더를 구성하지 못했습니다.")
        }
        writer.add(video)
        writer.add(audio)
        // Fragmented output improves the chance of recovery after an unexpected exit.
        writer.movieFragmentInterval = CMTime(seconds: 1, preferredTimescale: 600)
    }

    func start(at time: CMTime) throws {
        guard writer.startWriting() else {
            throw writer.error ?? RecorderError.message("녹화 파일을 열지 못했습니다.")
        }
        writer.startSession(atSourceTime: time)
    }

    func appendVideo(_ sample: CMSampleBuffer) throws -> Bool {
        if writer.status == .failed { throw writer.error ?? RecorderError.message("영상 저장에 실패했습니다.") }
        guard video.isReadyForMoreMediaData else { return false }
        guard video.append(sample) else { throw writer.error ?? RecorderError.message("영상 저장에 실패했습니다.") }
        videoCount += 1
        return true
    }

    func appendAudio(_ sample: CMSampleBuffer) throws {
        if writer.status == .failed { throw writer.error ?? RecorderError.message("음성 저장에 실패했습니다.") }
        guard audio.isReadyForMoreMediaData else { return }
        guard audio.append(sample) else { throw writer.error ?? RecorderError.message("음성 저장에 실패했습니다.") }
        audioCount += 1
    }

    func finish(completion: @escaping () -> Void) {
        guard writer.status == .writing else { completion(); return }
        video.markAsFinished()
        audio.markAsFinished()
        writer.finishWriting(completionHandler: completion)
    }

    func cancel() { writer.cancelWriting() }
}
