import AVFoundation
import Combine
import UIKit

enum CaptureState: Equatable {
    case preparing, ready, starting, recording, saving, unavailable
}

final class CaptureController: NSObject, ObservableObject {
    @Published private(set) var state: CaptureState = .preparing
    @Published private(set) var status = "카메라를 준비하고 있습니다."
    @Published private(set) var startedAt: Date?
    @Published private(set) var recordings: [Recording] = RecordingStore.load()
    @Published var errorMessage: String?

    let rearPreview = AVCaptureVideoPreviewLayer()
    let frontPreview = AVCaptureVideoPreviewLayer()

    private let session = AVCaptureMultiCamSession()
    private let queue = DispatchQueue(label: "app.dualcam.capture", qos: .userInitiated)
    private let rearOutput = AVCaptureVideoDataOutput()
    private let frontOutput = AVCaptureVideoDataOutput()
    private let audioOutput = AVCaptureAudioDataOutput()
    private var devices: [AVCaptureDevice] = []
    private var configured = false
    private var preparing = false
    private var foreground = true
    private var writer: DualMovieWriter?
    private var currentID: UUID?
    private var currentDate: Date?
    private var saveInProgress = false
    private var announcedRecording = false
    private var saveCallbacks: [() -> Void] = []
    private var watchdog: DispatchSourceTimer?
    private var observers: [NSObjectProtocol] = []

    override init() {
        super.init()
        rearPreview.videoGravity = .resizeAspectFill
        frontPreview.videoGravity = .resizeAspectFill
        observeSession()
    }

    deinit {
        watchdog?.cancel()
        for observer in observers { NotificationCenter.default.removeObserver(observer) }
    }

    @MainActor func prepare() async {
        guard !preparing else { return }
        preparing = true
        guard AVCaptureMultiCamSession.isMultiCamSupported else {
            update(.unavailable, "이 아이폰은 전·후면 동시 카메라를 지원하지 않습니다.")
            return
        }
        let cameraAllowed = await AVCaptureDevice.requestAccess(for: .video)
        let microphoneAllowed = await AVCaptureDevice.requestAccess(for: .audio)
        guard cameraAllowed, microphoneAllowed else {
            update(.unavailable, "설정 → DualCam에서 카메라와 마이크 접근을 허용해 주세요.")
            return
        }
        queue.async { [weak self] in
            guard let self else { return }
            do {
                try self.configure()
                self.configured = true
                if self.foreground {
                    try self.startSession()
                    self.update(.ready, "전·후면 카메라와 마이크 준비 완료")
                }
            } catch {
                self.update(.unavailable, error.localizedDescription)
            }
        }
    }

    func startRecording() {
        queue.async { [weak self] in
            guard let self, self.configured, self.foreground,
                  self.session.isRunning, self.writer == nil, !self.saveInProgress else { return }
            do {
                guard RecordingStore.freeBytes() >= 200 * 1_024 * 1_024 else {
                    throw RecorderError.message("저장 공간이 부족합니다. 최소 200MB를 확보해 주세요.")
                }
                let id = UUID()
                let folder = try RecordingStore.createFolder(id: id)
                self.writer = DualMovieWriter(folder: folder)
                self.currentID = id
                self.currentDate = Date()
                self.announcedRecording = false
                self.update(.starting, "두 카메라와 마이크의 첫 데이터를 기다리는 중")
                self.startWatchdog()
                self.queue.asyncAfter(deadline: .now() + 6) { [weak self] in
                    guard let self, self.currentID == id, let writer = self.writer,
                          writer.duration == 0 else { return }
                    self.stopOnQueue(reason: "카메라·마이크에서 데이터를 받지 못해 녹화를 종료했습니다.")
                }
            } catch { self.showError(error.localizedDescription) }
        }
    }

    func stopRecording() { queue.async { [weak self] in self?.stopOnQueue() } }

    @MainActor func retry() {
        preparing = false
        Task { await prepare() }
    }

    /// Called on the main thread before the app loses active status.
    func suspend() {
        let task = UIApplication.shared.beginBackgroundTask(withName: "Finish dual recording")
        queue.async { [weak self] in
            guard let self else {
                DispatchQueue.main.async { if task != .invalid { UIApplication.shared.endBackgroundTask(task) } }
                return
            }
            self.foreground = false
            self.stopOnQueue {
                if task != .invalid { UIApplication.shared.endBackgroundTask(task) }
            }
            if self.session.isRunning { self.session.stopRunning() }
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }

    func resume() {
        queue.async { [weak self] in
            guard let self else { return }
            self.foreground = true
            guard self.configured else { return }
            do {
                if !self.session.isRunning { try self.startSession() }
                if self.writer == nil, !self.saveInProgress {
                    self.update(.ready, "전·후면 카메라와 마이크 준비 완료")
                }
            } catch { self.update(.unavailable, error.localizedDescription) }
        }
    }

    func refreshRecordings() { recordings = RecordingStore.load() }

    func delete(_ recording: Recording) {
        do { try RecordingStore.delete(recording); refreshRecordings() }
        catch { errorMessage = error.localizedDescription }
    }

    private func configure() throws {
        guard let rear = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
              let front = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front),
              let microphone = AVCaptureDevice.default(for: .audio) else {
            throw RecorderError.message("전면·후면 카메라 또는 마이크를 찾지 못했습니다.")
        }
        let discovery = AVCaptureDevice.DiscoverySession(
            deviceTypes: [.builtInWideAngleCamera], mediaType: .video, position: .unspecified)
        guard discovery.supportedMultiCamDeviceSets.contains(where: { $0.contains(rear) && $0.contains(front) }) else {
            throw RecorderError.message("이 아이폰의 전·후면 카메라 조합은 동시 녹화를 지원하지 않습니다.")
        }
        devices = [rear, front]
        session.automaticallyConfiguresApplicationAudioSession = false
        if session.isRunning { session.stopRunning() }
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        for connection in session.connections { session.removeConnection(connection) }
        for output in session.outputs { session.removeOutput(output) }
        for input in session.inputs { session.removeInput(input) }
        for device in devices { try setFormat(device, maxWidth: 1_280, maxHeight: 720) }
        rearPreview.setSessionWithNoConnection(session)
        frontPreview.setSessionWithNoConnection(session)
        try addCamera(rear, output: rearOutput, preview: rearPreview)
        try addCamera(front, output: frontOutput, preview: frontPreview)

        let input = try AVCaptureDeviceInput(device: microphone)
        guard session.canAddInput(input), session.canAddOutput(audioOutput) else {
            throw RecorderError.message("마이크 입력을 추가할 수 없습니다.")
        }
        session.addInputWithNoConnections(input)
        session.addOutputWithNoConnections(audioOutput)
        guard let port = input.ports.first(where: { $0.mediaType == .audio }) else {
            throw RecorderError.message("마이크 연결을 찾지 못했습니다.")
        }
        let connection = AVCaptureConnection(inputPorts: [port], output: audioOutput)
        guard session.canAddConnection(connection) else { throw RecorderError.message("마이크를 연결할 수 없습니다.") }
        session.addConnection(connection)
        audioOutput.setSampleBufferDelegate(self, queue: queue)
        if session.hardwareCost > 1 {
            for device in devices { try setFormat(device, maxWidth: 640, maxHeight: 480) }
        }
        guard session.hardwareCost <= 1 else {
            throw RecorderError.message("이 기기에서 두 카메라의 처리 한도를 초과했습니다.")
        }
    }

    private func setFormat(_ device: AVCaptureDevice, maxWidth: Int32, maxHeight: Int32) throws {
        let formats = device.formats.filter { format in
            let size = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
            return format.isMultiCamSupported && size.width <= maxWidth && size.height <= maxHeight
                && size.width >= 640 && size.height >= 480
                && format.videoSupportedFrameRateRanges.contains { $0.minFrameRate <= 30 && $0.maxFrameRate >= 30 }
        }.sorted {
            let a = CMVideoFormatDescriptionGetDimensions($0.formatDescription)
            let b = CMVideoFormatDescriptionGetDimensions($1.formatDescription)
            return a.width * a.height > b.width * b.height
        }
        guard let format = formats.first else {
            throw RecorderError.message("동시 녹화용 720p 또는 480p·30fps 형식을 찾지 못했습니다.")
        }
        try device.lockForConfiguration()
        defer { device.unlockForConfiguration() }
        device.activeFormat = format
        device.activeVideoMinFrameDuration = CMTime(value: 1, timescale: 30)
        device.activeVideoMaxFrameDuration = CMTime(value: 1, timescale: 30)
    }

    private func addCamera(_ device: AVCaptureDevice, output: AVCaptureVideoDataOutput,
                           preview: AVCaptureVideoPreviewLayer) throws {
        let input = try AVCaptureDeviceInput(device: device)
        guard session.canAddInput(input), session.canAddOutput(output) else {
            throw RecorderError.message("카메라 입출력을 추가하지 못했습니다.")
        }
        session.addInputWithNoConnections(input)
        session.addOutputWithNoConnections(output)
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarFullRange]
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: queue)
        guard let port = input.ports(for: .video, sourceDeviceType: device.deviceType,
                                     sourceDevicePosition: device.position).first else {
            throw RecorderError.message("카메라 연결을 찾지 못했습니다.")
        }
        let dataConnection = AVCaptureConnection(inputPorts: [port], output: output)
        let previewConnection = AVCaptureConnection(inputPort: port, videoPreviewLayer: preview)
        for connection in [dataConnection, previewConnection] {
            guard session.canAddConnection(connection) else { throw RecorderError.message("카메라를 연결하지 못했습니다.") }
            session.addConnection(connection)
            if connection.isVideoOrientationSupported { connection.videoOrientation = .portrait }
            if connection.isVideoMirroringSupported {
                connection.automaticallyAdjustsVideoMirroring = false
                connection.isVideoMirrored = (connection === previewConnection && device.position == .front)
            }
            if connection.isVideoStabilizationSupported { connection.preferredVideoStabilizationMode = .off }
        }
    }

    private func startSession() throws {
        let audio = AVAudioSession.sharedInstance()
        try audio.setCategory(.playAndRecord, mode: .videoRecording, options: [.defaultToSpeaker])
        try audio.setActive(true)
        session.startRunning()
        guard session.isRunning else { throw RecorderError.message("카메라 세션을 시작하지 못했습니다.") }
    }

    private func stopOnQueue(reason: String? = nil, completion: (() -> Void)? = nil) {
        if let completion { saveCallbacks.append(completion) }
        guard let writer, let id = currentID, let date = currentDate else {
            if !saveInProgress { finishCallbacks() }
            if let reason { showError(reason) }
            return
        }
        self.writer = nil
        currentID = nil
        currentDate = nil
        watchdog?.cancel()
        watchdog = nil
        saveInProgress = true
        update(.saving, "두 영상을 저장하고 있습니다.")
        writer.finish(on: queue) { [weak self] result in
            guard let self else { return }
            self.saveInProgress = false
            var errorText = reason
            switch result {
            case .success(let duration):
                do { try RecordingStore.save(Recording(id: id, createdAt: date, duration: duration)) }
                catch { errorText = "영상은 저장됐지만 목록을 갱신하지 못했습니다. 파일 앱에서 확인해 주세요.\n\(error.localizedDescription)" }
            case .failure(let error):
                errorText = [reason, error.localizedDescription].compactMap { $0 }.joined(separator: "\n")
            }
            let ready = self.foreground && self.session.isRunning
            self.update(ready ? .ready : (self.foreground ? .unavailable : .preparing),
                        ready ? "저장 완료 · 다시 녹화할 수 있습니다." : "녹화가 종료됐습니다. 화면을 다시 열거나 재시도해 주세요.")
            DispatchQueue.main.async {
                self.startedAt = nil
                self.refreshRecordings()
                if let errorText { self.errorMessage = errorText }
            }
            self.finishCallbacks()
        }
    }

    private func finishCallbacks() {
        let callbacks = saveCallbacks
        saveCallbacks.removeAll()
        DispatchQueue.main.async { callbacks.forEach { $0() } }
    }

    private func startWatchdog() {
        let timer = DispatchSource.makeTimerSource(queue: queue)
        timer.schedule(deadline: .now() + 2, repeating: 2)
        timer.setEventHandler { [weak self] in
            guard let self, self.writer != nil else { return }
            if RecordingStore.freeBytes() < 80 * 1_024 * 1_024 {
                self.stopOnQueue(reason: "저장 공간이 부족해 녹화를 종료했습니다.")
            } else if ProcessInfo.processInfo.thermalState == .critical || self.devices.contains(where: {
                $0.systemPressureState.level == .critical || $0.systemPressureState.level == .shutdown
            }) {
                self.stopOnQueue(reason: "기기 온도가 높아 녹화를 종료했습니다.")
            }
        }
        watchdog = timer
        timer.resume()
    }

    private func observeSession() {
        let center = NotificationCenter.default
        observers.append(center.addObserver(forName: AVAudioSession.interruptionNotification,
                                             object: AVAudioSession.sharedInstance(), queue: nil) { [weak self] notification in
            guard let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  AVAudioSession.InterruptionType(rawValue: raw) == .began else { return }
            self?.queue.async { [weak self] in self?.stopOnQueue(reason: "오디오 사용이 중단되어 녹화를 종료했습니다.") }
        })
        observers.append(center.addObserver(forName: AVCaptureSession.wasInterruptedNotification,
                                             object: session, queue: nil) { [weak self] _ in
            self?.queue.async { [weak self] in self?.stopOnQueue(reason: "전화 또는 다른 카메라 사용으로 녹화가 중단됐습니다.") }
        })
        observers.append(center.addObserver(forName: AVCaptureSession.runtimeErrorNotification,
                                             object: session, queue: nil) { [weak self] notification in
            let error = notification.userInfo?[AVCaptureSessionErrorKey] as? Error
            self?.queue.async { [weak self] in
                guard let self else { return }
                let message = error?.localizedDescription ?? "카메라 세션 오류가 발생했습니다."
                self.stopOnQueue(reason: message)
                self.update(.unavailable, message)
            }
        })
        observers.append(center.addObserver(forName: AVCaptureSession.interruptionEndedNotification,
                                             object: session, queue: nil) { [weak self] _ in self?.resumeIfForeground() })
    }

    private func resumeIfForeground() {
        queue.async { [weak self] in
            guard let self, self.foreground, self.configured else { return }
            do {
                try self.startSession()
                if !self.saveInProgress { self.update(.ready, "전·후면 카메라와 마이크 준비 완료") }
            } catch { self.update(.unavailable, error.localizedDescription) }
        }
    }

    private func update(_ state: CaptureState, _ text: String) {
        DispatchQueue.main.async { self.state = state; self.status = text }
    }

    private func showError(_ text: String) { DispatchQueue.main.async { self.errorMessage = text } }
}

extension CaptureController: AVCaptureVideoDataOutputSampleBufferDelegate, AVCaptureAudioDataOutputSampleBufferDelegate {
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard let writer else { return }
        do {
            if output === audioOutput { try writer.appendAudio(sampleBuffer) }
            else { try writer.appendVideo(sampleBuffer, side: output === frontOutput ? .front : .rear) }
            if writer.duration > 0, let date = currentDate {
                if !announcedRecording {
                    announcedRecording = true
                    DispatchQueue.main.async { self.startedAt = date }
                    update(.recording, "전면 + 후면 · 음성 녹음 중")
                }
            }
        } catch {
            stopOnQueue(reason: "녹화를 종료했습니다.\n\(error.localizedDescription)")
        }
    }
}
