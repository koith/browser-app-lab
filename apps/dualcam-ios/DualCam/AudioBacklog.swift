/// A bounded FIFO: temporary encoder backpressure must not silently discard audio.
struct AudioBacklog<Sample> {
    private var samples: [Sample] = []
    let limit: Int

    var isEmpty: Bool { samples.isEmpty }
    var count: Int { samples.count }

    mutating func enqueue(_ sample: Sample) throws {
        guard samples.count < limit else {
            throw RecorderError.message("음성 인코더의 지연이 길어 녹화를 종료합니다. 기기를 식힌 뒤 다시 시도해 주세요.")
        }
        samples.append(sample)
    }

    mutating func drain(ready: () -> Bool, write: (Sample) throws -> Void) throws {
        while let sample = samples.first, ready() {
            try write(sample)
            samples.removeFirst()
        }
    }
}
